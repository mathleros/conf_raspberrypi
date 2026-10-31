"""Typed, hardware-independent contracts for human-marker observations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Protocol, TypeGuard

from irobot.config.settings import MarkerIdentity, RuntimeSettings


class ObservationDisposition(str, Enum):
    VALID = "valid"
    ABSENT = "absent"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"
    STALE = "stale"
    FAULT = "fault"


class AcquisitionStatus(str, Enum):
    CONFIRMING = "confirming"
    ACQUIRED = "acquired"
    REJECTED = "rejected"


class AcquisitionReason(str, Enum):
    WAITING_FOR_CONFIRMATIONS = "waiting_for_confirmations"
    ACQUIRED = "acquired"
    OBSERVATION_ABSENT = "observation_absent"
    OBSERVATION_AMBIGUOUS = "observation_ambiguous"
    OBSERVATION_REJECTED = "observation_rejected"
    PERCEPTION_FAULT = "perception_fault"
    STALE = "stale"
    TIMESTAMP_INCOHERENT = "timestamp_incoherent"
    MISSION_MISMATCH = "mission_mismatch"
    CONTEXT_MISMATCH = "context_mismatch"
    IDENTITY_MISMATCH = "identity_mismatch"
    STREAM_CHANGED = "stream_changed"
    DUPLICATE_FRAME = "duplicate_frame"
    FRAME_OUT_OF_ORDER = "frame_out_of_order"
    FRAME_GAP = "frame_gap"
    GEOMETRY_INVALID = "geometry_invalid"


@dataclass(frozen=True)
class MarkerQuality:
    corners_visible: bool
    geometry_valid: bool
    blur_metric: float | None = None
    reprojection_error_px: float | None = None
    obliqueness_deg: float | None = None


@dataclass(frozen=True)
class MarkerObservation:
    """Atomic sample; monotonic timestamps, centimetres, and signed bearing degrees."""

    source_id: str
    stream_generation: str
    frame_number: int
    captured_at: float
    published_at: float
    mission_id: str
    context_version: str
    disposition: ObservationDisposition
    identity: MarkerIdentity | None = None
    image_width_px: int | None = None
    image_height_px: int | None = None
    center_x_px: float | None = None
    center_y_px: float | None = None
    bearing_deg: float | None = None
    optical_distance_cm: float | None = None
    robot_clearance_cm: float | None = None
    calibration_version: str | None = None
    quality: MarkerQuality | None = None
    reason: str | None = None


@dataclass(frozen=True)
class AcquisitionAssessment:
    status: AcquisitionStatus
    reason: AcquisitionReason
    confirmations: int
    detail: str | None = None


@dataclass(frozen=True)
class ArucoFrameDetection:
    disposition: ObservationDisposition
    identity: MarkerIdentity | None = None
    corners_px: tuple[tuple[float, float], ...] | None = None
    reason: str | None = None


@dataclass(frozen=True)
class HumanMarkerMissionContext:
    """Immutable mission snapshot of the configured marker identity and context."""

    mission_id: str
    context_version: str
    identity: MarkerIdentity

    def __post_init__(self) -> None:
        if (not isinstance(self.mission_id, str) or not self.mission_id
                or not isinstance(self.context_version, str) or not self.context_version
                or not isinstance(self.identity, MarkerIdentity)):
            raise ValueError("Human marker mission context must be explicit")

    @classmethod
    def from_runtime_settings(
        cls,
        settings: RuntimeSettings,
        *,
        mission_id: str,
        context_version: str,
    ) -> "HumanMarkerMissionContext":
        if not isinstance(settings, RuntimeSettings):
            raise TypeError("Human marker context requires RuntimeSettings")
        if settings.human_marker_identity is None:
            raise ValueError("Human marker identity is not configured")
        return cls(mission_id, context_version, settings.human_marker_identity)

    def new_acquisition(self, *, max_age_seconds: float) -> "HumanMarkerAcquisition":
        return HumanMarkerAcquisition(
            expected_identity=self.identity,
            mission_id=self.mission_id,
            context_version=self.context_version,
            max_age_seconds=max_age_seconds,
        )


@dataclass(frozen=True)
class HumanPerceptionFrame:
    """Opaque pixels with capture-owned source, sequence, and monotonic timestamps."""

    source_id: str
    stream_generation: str
    frame_number: int
    captured_at: float
    published_at: float
    image: object


class HumanPerceptionProvider(Protocol):
    def observe(
        self, frame: HumanPerceptionFrame, *,
        context: HumanMarkerMissionContext,
    ) -> MarkerObservation: ...


class ArucoDetectorBackend(Protocol):
    def detectMarkers(self, image: object) -> tuple[object, object, object]: ...


class OpenCVArucoMarkerDecoder:
    """Decode one configured ArUco ID; geometry/calibration remain separate."""

    def __init__(
        self,
        identity: MarkerIdentity,
        *,
        aruco_api: object | None = None,
    ) -> None:
        if identity.family != "aruco":
            raise ValueError("The configured marker family is not ArUco")
        if (not identity.identifier.isascii() or not identity.identifier.isdigit()
                or str(int(identity.identifier)) != identity.identifier):
            raise ValueError("ArUco identifier must be a canonical non-negative integer")
        if aruco_api is None:
            import cv2

            aruco_api = getattr(cv2, "aruco", None)
        if aruco_api is None:
            raise RuntimeError("OpenCV ArUco API is unavailable; no fallback detector is selected")

        get_dictionary = getattr(aruco_api, "getPredefinedDictionary", None)
        parameters_factory = getattr(aruco_api, "DetectorParameters", None)
        detector_factory = getattr(aruco_api, "ArucoDetector", None)
        dictionary_code = getattr(aruco_api, identity.dictionary, None)
        if (not callable(get_dictionary) or not callable(parameters_factory)
                or not callable(detector_factory) or isinstance(dictionary_code, bool)
                or not isinstance(dictionary_code, int)):
            raise ValueError(f"Unsupported OpenCV ArUco dictionary/API: {identity.dictionary}")

        dictionary = get_dictionary(dictionary_code)
        detector = detector_factory(dictionary, parameters_factory())
        if not callable(getattr(detector, "detectMarkers", None)):
            raise RuntimeError("OpenCV ArUco detector lacks detectMarkers")
        self.identity = identity
        self.expected_id = int(identity.identifier)
        self._detector: ArucoDetectorBackend = detector

    def detect(self, image: object) -> ArucoFrameDetection:
        corners_raw, ids_raw, _rejected = self._detector.detectMarkers(image)
        corners = self._as_python_values(corners_raw)
        marker_ids = self._flatten_ids(ids_raw)
        if marker_ids is None:
            return ArucoFrameDetection(
                ObservationDisposition.FAULT, reason="malformed_marker_ids",
            )
        if not marker_ids:
            if corners not in (None, []):
                return ArucoFrameDetection(
                    ObservationDisposition.FAULT, reason="corners_without_marker_ids",
                )
            return ArucoFrameDetection(ObservationDisposition.ABSENT)
        if not isinstance(corners, list) or len(corners) != len(marker_ids):
            return ArucoFrameDetection(
                ObservationDisposition.FAULT, reason="marker_id_corner_count_mismatch",
            )

        matches = [index for index, marker_id in enumerate(marker_ids) if marker_id == self.expected_id]
        if not matches:
            return ArucoFrameDetection(ObservationDisposition.ABSENT)
        if len(matches) > 1:
            return ArucoFrameDetection(
                ObservationDisposition.AMBIGUOUS,
                identity=self.identity,
                reason="multiple_configured_markers",
            )
        parsed_corners = self._parse_corners(corners[matches[0]])
        if parsed_corners is None:
            return ArucoFrameDetection(
                ObservationDisposition.REJECTED,
                identity=self.identity,
                reason="malformed_marker_corners",
            )
        return ArucoFrameDetection(
            ObservationDisposition.VALID,
            identity=self.identity,
            corners_px=parsed_corners,
        )

    @classmethod
    def _as_python_values(cls, value: object) -> object:
        tolist = getattr(value, "tolist", None)
        if callable(tolist):
            return cls._as_python_values(tolist())
        if isinstance(value, (tuple, list)):
            return [cls._as_python_values(item) for item in value]
        return value

    @classmethod
    def _flatten_ids(cls, values: object) -> list[int] | None:
        normalized = cls._as_python_values(values)
        if normalized is None:
            return []
        flattened: list[int] = []

        def append(value: object) -> bool:
            if isinstance(value, list):
                return all(append(item) for item in value)
            if isinstance(value, int) and not isinstance(value, bool):
                flattened.append(value)
                return True
            return False

        return flattened if append(normalized) else None

    @classmethod
    def _parse_corners(cls, value: object) -> tuple[tuple[float, float], ...] | None:
        points = cls._as_python_values(value)
        while isinstance(points, list) and len(points) == 1 and isinstance(points[0], list):
            points = points[0]
        if not isinstance(points, list) or len(points) != 4:
            return None
        parsed: list[tuple[float, float]] = []
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                return None
            x, y = point
            if not HumanMarkerAcquisition._finite(x) or not HumanMarkerAcquisition._finite(y):
                return None
            parsed.append((float(x), float(y)))
        return tuple(parsed)


class HumanMarkerAcquisition:
    """Confirm one configured marker from fresh consecutive frames in one context."""

    MAX_AGE_TARGET_SECONDS = 0.2
    REQUIRED_CONFIRMATIONS = 3

    def __init__(
        self,
        *,
        expected_identity: MarkerIdentity,
        mission_id: str,
        context_version: str,
        max_age_seconds: float,
    ) -> None:
        if (not isinstance(expected_identity, MarkerIdentity)
                or not isinstance(mission_id, str) or not mission_id
                or not isinstance(context_version, str) or not context_version):
            raise ValueError("Mission and context identifiers must be explicit")
        if not self._finite(max_age_seconds) or max_age_seconds <= 0:
            raise ValueError("Observation freshness budget must be explicit and positive")
        self.expected_identity = expected_identity
        self.mission_id = mission_id
        self.context_version = context_version
        self.max_age_seconds = float(max_age_seconds)
        self._source_id: str | None = None
        self._stream_generation: str | None = None
        self._last_frame_number: int | None = None
        self._last_captured_at: float | None = None
        self._last_published_at: float | None = None
        self._confirmations = 0

    def reset(self) -> None:
        self._source_id = None
        self._stream_generation = None
        self._last_frame_number = None
        self._last_captured_at = None
        self._last_published_at = None
        self._confirmations = 0

    def observe(self, observation: MarkerObservation, *, now: float) -> AcquisitionAssessment:
        if not isinstance(observation, MarkerObservation):
            return self._reject(AcquisitionReason.OBSERVATION_REJECTED)
        if not self._finite(now):
            return self._reject(AcquisitionReason.TIMESTAMP_INCOHERENT)
        if observation.mission_id != self.mission_id:
            return self._reject(AcquisitionReason.MISSION_MISMATCH)
        if observation.context_version != self.context_version:
            return self._reject(AcquisitionReason.CONTEXT_MISMATCH)
        if not self._timestamps_are_coherent(observation, now):
            return self._reject(AcquisitionReason.TIMESTAMP_INCOHERENT)
        if now - observation.captured_at > self.max_age_seconds:
            return self._reject(AcquisitionReason.STALE)

        sequence_reason = self._check_sequence(observation)
        if sequence_reason is not None:
            return self._reject(sequence_reason)

        disposition_reasons = {
            ObservationDisposition.ABSENT: AcquisitionReason.OBSERVATION_ABSENT,
            ObservationDisposition.AMBIGUOUS: AcquisitionReason.OBSERVATION_AMBIGUOUS,
            ObservationDisposition.REJECTED: AcquisitionReason.OBSERVATION_REJECTED,
            ObservationDisposition.STALE: AcquisitionReason.STALE,
            ObservationDisposition.FAULT: AcquisitionReason.PERCEPTION_FAULT,
        }
        if observation.disposition is not ObservationDisposition.VALID:
            return self._reject(
                disposition_reasons.get(
                    observation.disposition, AcquisitionReason.OBSERVATION_REJECTED,
                ),
                detail=observation.reason,
            )
        if observation.identity != self.expected_identity:
            return self._reject(AcquisitionReason.IDENTITY_MISMATCH)
        if not self._geometry_is_valid(observation):
            return self._reject(AcquisitionReason.GEOMETRY_INVALID)

        self._confirmations += 1
        if self._confirmations >= self.REQUIRED_CONFIRMATIONS:
            return AcquisitionAssessment(
                AcquisitionStatus.ACQUIRED, AcquisitionReason.ACQUIRED, self._confirmations,
            )
        return AcquisitionAssessment(
            AcquisitionStatus.CONFIRMING,
            AcquisitionReason.WAITING_FOR_CONFIRMATIONS,
            self._confirmations,
        )

    def _check_sequence(self, observation: MarkerObservation) -> AcquisitionReason | None:
        source_id = observation.source_id
        generation = observation.stream_generation
        frame_number = observation.frame_number
        if (not isinstance(source_id, str) or not source_id
                or not isinstance(generation, str) or not generation
                or isinstance(frame_number, bool) or not isinstance(frame_number, int)
                or frame_number < 0):
            self.reset()
            return AcquisitionReason.FRAME_OUT_OF_ORDER

        if self._source_id is None:
            self._source_id = source_id
            self._stream_generation = generation
        elif (source_id != self._source_id or generation != self._stream_generation):
            self._source_id = source_id
            self._stream_generation = generation
            self._last_frame_number = frame_number
            self._last_captured_at = observation.captured_at
            self._last_published_at = observation.published_at
            self._confirmations = 0
            return AcquisitionReason.STREAM_CHANGED

        previous = self._last_frame_number
        if previous is not None:
            if self._last_captured_at is None or self._last_published_at is None:
                self.reset()
                return AcquisitionReason.TIMESTAMP_INCOHERENT
            if frame_number == previous:
                self._confirmations = 0
                return AcquisitionReason.DUPLICATE_FRAME
            if frame_number < previous:
                self._confirmations = 0
                return AcquisitionReason.FRAME_OUT_OF_ORDER
            if frame_number != previous + 1:
                self._last_frame_number = frame_number
                self._last_captured_at = observation.captured_at
                self._last_published_at = observation.published_at
                self._confirmations = 0
                return AcquisitionReason.FRAME_GAP
            if (observation.captured_at < self._last_captured_at
                    or observation.published_at < self._last_published_at):
                self._last_frame_number = frame_number
                self._last_captured_at = observation.captured_at
                self._last_published_at = observation.published_at
                self._confirmations = 0
                return AcquisitionReason.TIMESTAMP_INCOHERENT

        self._last_frame_number = frame_number
        self._last_captured_at = observation.captured_at
        self._last_published_at = observation.published_at
        return None

    def _reject(
        self,
        reason: AcquisitionReason,
        *,
        detail: str | None = None,
    ) -> AcquisitionAssessment:
        self._confirmations = 0
        return AcquisitionAssessment(
            AcquisitionStatus.REJECTED, reason, self._confirmations, detail,
        )

    @classmethod
    def _timestamps_are_coherent(cls, observation: MarkerObservation, now: float) -> bool:
        times = (observation.captured_at, observation.published_at, now)
        return (
            all(cls._finite(value) for value in times)
            and observation.captured_at <= observation.published_at <= now
        )

    @staticmethod
    def _finite(value: object) -> TypeGuard[int | float]:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        try:
            return math.isfinite(value)
        except OverflowError:
            return False

    @classmethod
    def _geometry_is_valid(cls, observation: MarkerObservation) -> bool:
        quality = observation.quality
        if (not isinstance(quality, MarkerQuality) or quality.corners_visible is not True
                or quality.geometry_valid is not True):
            return False
        if not isinstance(observation.calibration_version, str) or not observation.calibration_version:
            return False
        if (isinstance(observation.image_width_px, bool)
                or not isinstance(observation.image_width_px, int)
                or observation.image_width_px <= 0
                or isinstance(observation.image_height_px, bool)
                or not isinstance(observation.image_height_px, int)
                or observation.image_height_px <= 0):
            return False
        center_x = observation.center_x_px
        center_y = observation.center_y_px
        optical_distance = observation.optical_distance_cm
        robot_clearance = observation.robot_clearance_cm
        if (not cls._finite(center_x) or not cls._finite(center_y)
                or not cls._finite(observation.bearing_deg)
                or not cls._finite(optical_distance) or not cls._finite(robot_clearance)):
            return False
        if (center_x < 0 or center_x > observation.image_width_px
                or center_y < 0 or center_y > observation.image_height_px
                or optical_distance <= 0 or robot_clearance <= 0):
            return False
        for metric in (
            quality.blur_metric, quality.reprojection_error_px, quality.obliqueness_deg,
        ):
            if metric is not None and (not cls._finite(metric) or metric < 0):
                return False
        return True
