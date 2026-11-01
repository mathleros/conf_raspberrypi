"""Public perception contracts, provenance validation and marker acquisition."""

from __future__ import annotations

from collections import deque

from irobot.config.settings import MarkerIdentity, RuntimeSettings
from irobot.interfaces.aruco_marker_decoder import OpenCVArucoMarkerDecoder
from irobot.interfaces.human_perception_contracts import (
    AcquisitionAssessment, AcquisitionReason, AcquisitionStatus, ArucoDetectorBackend,
    ArucoFrameDetection, HumanMarkerMissionContext, HumanPerceptionFrame,
    HumanPerceptionFrameSource, HumanPerceptionProvider, HumanPerceptionStreamFault,
    MarkerObservation, MarkerQuality, ObservationDisposition, finite_number,
)


def validate_marker_observation(
    frame: HumanPerceptionFrame, observation: MarkerObservation, *,
    context: HumanMarkerMissionContext, now: float,
) -> MarkerObservation:
    """Validate provenance without changing timestamps, inferring geometry, or aging policy."""
    if not isinstance(frame, HumanPerceptionFrame):
        raise TypeError("Perception input must be a HumanPerceptionFrame")
    if not isinstance(context, HumanMarkerMissionContext):
        raise TypeError("Perception context must be a HumanMarkerMissionContext")
    if not isinstance(observation, MarkerObservation):
        raise TypeError("Perception result must be a MarkerObservation")
    for sample in (frame, observation):
        _validate_sample(sample, now)
    for name in ("source_id", "stream_generation", "frame_number", "captured_at"):
        if getattr(observation, name) != getattr(frame, name):
            raise ValueError(f"Observation {name} does not match the supplied frame")
    if observation.published_at < frame.published_at:
        raise ValueError("Observation publication precedes frame publication")
    for name in ("mission_id", "context_version"):
        value = getattr(observation, name)
        if not isinstance(value, str) or not value or value != getattr(context, name):
            raise ValueError(f"Observation {name} does not match the requested context")
    if not isinstance(observation.disposition, ObservationDisposition):
        raise ValueError("Observation disposition must be an ObservationDisposition")
    if observation.identity is not None:
        if (not isinstance(observation.identity, MarkerIdentity)
                or observation.identity != context.identity):
            raise ValueError("Observation identity does not match the requested context")
    _validate_observation_fields(observation)
    return observation


def _validate_sample(sample: HumanPerceptionFrame | MarkerObservation, now: float) -> None:
    for name in ("source_id", "stream_generation"):
        value = getattr(sample, name)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{type(sample).__name__}.{name} must be explicit")
    if (isinstance(sample.frame_number, bool)
            or not isinstance(sample.frame_number, int) or sample.frame_number < 0):
        raise ValueError(f"{type(sample).__name__}.frame_number must be a non-negative integer")
    if not HumanMarkerAcquisition._timestamps_are_coherent(sample, now):
        raise ValueError(f"{type(sample).__name__} timestamps are incoherent")


def _validate_observation_fields(observation: MarkerObservation) -> None:
    for name in ("image_width_px", "image_height_px"):
        value = getattr(observation, name)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            raise ValueError(f"Observation {name} must be an integer or None")
    for name in (
        "center_x_px", "center_y_px", "bearing_deg",
        "optical_distance_cm", "robot_clearance_cm",
    ):
        value = getattr(observation, name)
        if value is not None and not finite_number(value):
            raise ValueError(f"Observation {name} must be finite or None")
    for name in ("calibration_version", "reason"):
        value = getattr(observation, name)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Observation {name} must be a string or None")
    quality = observation.quality
    if quality is not None:
        if (not isinstance(quality, MarkerQuality)
                or not isinstance(quality.corners_visible, bool)
                or not isinstance(quality.geometry_valid, bool)):
            raise ValueError("Observation quality must be a typed MarkerQuality or None")
        for name in ("blur_metric", "reprojection_error_px", "obliqueness_deg"):
            value = getattr(quality, name)
            if value is not None and not finite_number(value):
                raise ValueError(f"Observation quality {name} must be finite or None")


class HumanMarkerAcquisition:
    """Confirm one configured marker from fresh consecutive frames in one context."""

    MAX_AGE_TARGET_SECONDS = 0.2
    REQUIRED_CONFIRMATIONS = 3
    _finite = staticmethod(finite_number)

    def __init__(
        self, *, expected_identity: MarkerIdentity, mission_id: str,
        context_version: str, max_age_seconds: float,
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
        self._confirmation_captures: deque[float] = deque(maxlen=self.REQUIRED_CONFIRMATIONS)

    def reset(self) -> None:
        self._source_id = None
        self._stream_generation = None
        self._last_frame_number = None
        self._last_captured_at = None
        self._last_published_at = None
        self._confirmation_captures.clear()

    def observe_frame(
        self, frame: HumanPerceptionFrame, observation: MarkerObservation, *, now: float,
    ) -> AcquisitionAssessment:
        """Validate a frame-bound result before applying the existing acquisition rules."""
        context = HumanMarkerMissionContext(
            self.mission_id, self.context_version, self.expected_identity,
        )
        try:
            validate_marker_observation(frame, observation, context=context, now=now)
        except (TypeError, ValueError):
            self._confirmation_captures.clear()
            raise
        return self.observe(observation, now=now)

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
        rejection = self._assess_marker(observation)
        if rejection is not None:
            return rejection
        return self._confirm(observation, now=now)

    def _assess_marker(self, observation: MarkerObservation) -> AcquisitionAssessment | None:
        if not isinstance(observation.disposition, ObservationDisposition):
            return self._reject(
                AcquisitionReason.OBSERVATION_REJECTED, detail="malformed_disposition",
            )
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
                ), detail=observation.reason,
            )
        if observation.identity != self.expected_identity:
            return self._reject(AcquisitionReason.IDENTITY_MISMATCH)
        if not self._geometry_is_valid(observation):
            return self._reject(AcquisitionReason.GEOMETRY_INVALID)
        return None

    def _confirm(self, observation: MarkerObservation, *, now: float) -> AcquisitionAssessment:
        if len(self._confirmation_captures) < self.REQUIRED_CONFIRMATIONS:
            while (self._confirmation_captures
                   and now - self._confirmation_captures[0] > self.max_age_seconds):
                self._confirmation_captures.popleft()
        self._confirmation_captures.append(observation.captured_at)
        confirmations = len(self._confirmation_captures)
        if confirmations >= self.REQUIRED_CONFIRMATIONS:
            return AcquisitionAssessment(
                AcquisitionStatus.ACQUIRED, AcquisitionReason.ACQUIRED, confirmations,
            )
        return AcquisitionAssessment(
            AcquisitionStatus.CONFIRMING, AcquisitionReason.WAITING_FOR_CONFIRMATIONS,
            confirmations,
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
            self._record_frame(observation)
            self._confirmation_captures.clear()
            return AcquisitionReason.STREAM_CHANGED
        reason = self._check_previous_frame(observation)
        if reason is not None:
            return reason
        self._record_frame(observation)
        return None

    def _check_previous_frame(self, observation: MarkerObservation) -> AcquisitionReason | None:
        previous = self._last_frame_number
        if previous is None:
            return None
        if self._last_captured_at is None or self._last_published_at is None:
            self.reset()
            return AcquisitionReason.TIMESTAMP_INCOHERENT
        if observation.frame_number == previous:
            self._confirmation_captures.clear()
            return AcquisitionReason.DUPLICATE_FRAME
        if observation.frame_number < previous:
            self._confirmation_captures.clear()
            return AcquisitionReason.FRAME_OUT_OF_ORDER
        if observation.frame_number != previous + 1:
            self._record_frame(observation)
            self._confirmation_captures.clear()
            return AcquisitionReason.FRAME_GAP
        if (observation.captured_at < self._last_captured_at
                or observation.published_at < self._last_published_at):
            self._record_frame(observation)
            self._confirmation_captures.clear()
            return AcquisitionReason.TIMESTAMP_INCOHERENT
        return None

    def _record_frame(self, observation: MarkerObservation) -> None:
        self._last_frame_number = observation.frame_number
        self._last_captured_at = observation.captured_at
        self._last_published_at = observation.published_at

    def _reject(
        self, reason: AcquisitionReason, *, detail: str | None = None,
    ) -> AcquisitionAssessment:
        self._confirmation_captures.clear()
        return AcquisitionAssessment(AcquisitionStatus.REJECTED, reason, 0, detail)

    @classmethod
    def _timestamps_are_coherent(
        cls, observation: MarkerObservation | HumanPerceptionFrame, now: float,
    ) -> bool:
        times = (observation.captured_at, observation.published_at, now)
        return (
            all(cls._finite(value) for value in times)
            and observation.captured_at <= observation.published_at <= now
        )

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
