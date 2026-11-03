"""OpenCV ArUco detector for one configured marker identity."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Protocol

import cv2
import numpy as np
from numpy.typing import NDArray

from irobot.config.settings import MarkerIdentity, load_runtime_settings
from .detector import Detector
from irobot.interfaces.perception_contracts import ObjectDetection

logger = logging.getLogger(__name__)

MARKER_SIDE_CM = 8.0


def estimate_marker_distance_cm(
    corners_px: tuple[tuple[float, float], ...],
    focal_px: float,
    frame_size_px: tuple[int, int] | None = None,
    oriented_frame_size_px: tuple[int, int] | None = None,
) -> float | None:
    """Estimate direct range from pose, assuming centred optics without distortion."""
    if frame_size_px is None or oriented_frame_size_px is None:
        settings = load_runtime_settings()
        if oriented_frame_size_px is None:
            oriented_frame_size_px = settings.camera_oriented_frame_size_px
        if frame_size_px is None:
            frame_size_px = oriented_frame_size_px
    assert frame_size_px is not None
    assert oriented_frame_size_px is not None
    width, height = frame_size_px
    reference_width, reference_height = oriented_frame_size_px
    if width <= 0 or height <= 0 or reference_width <= 0 or reference_height <= 0:
        raise ValueError("Frame dimensions must be positive")
    corners = np.asarray(corners_px, dtype=np.float64)
    if corners.shape != (4, 2) or not np.isfinite(corners).all():
        return None
    contour = corners.astype(np.float32)
    if not cv2.isContourConvex(contour) or cv2.contourArea(contour) <= 0:
        return None
    half_side = MARKER_SIDE_CM / 2
    object_points = np.array(
        [
            (-half_side, -half_side, 0),
            (half_side, -half_side, 0),
            (half_side, half_side, 0),
            (-half_side, half_side, 0),
        ],
        dtype=np.float64,
    )
    camera_matrix = np.array(
        [
            (focal_px * width / reference_width, 0, width / 2),
            (0, focal_px * height / reference_height, height / 2),
            (0, 0, 1),
        ],
        dtype=np.float64,
    )
    try:
        success, _, translation = cv2.solvePnP(
            object_points, corners, camera_matrix, np.zeros(5),
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
    except cv2.error:
        logger.exception("Échec de l'estimation de pose ArUco.")
        return None
    if not success or not np.isfinite(translation).all() or translation[2, 0] <= 0:
        return None
    return float(np.linalg.norm(translation))


class ObservationDisposition(str, Enum):
    VALID = "valid"
    ABSENT = "absent"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"
    FAULT = "fault"


@dataclass(frozen=True, slots=True)
class ArucoFrameDetection:
    disposition: ObservationDisposition
    identity: MarkerIdentity | None = None
    corners_px: tuple[tuple[float, float], ...] | None = None
    reason: str | None = None
    distance_cm: float | None = None
    position: str = "UNKNOWN"
    bbox_px: tuple[int, int, int, int] | None = None
    confidence: float = 0.0

    def as_object_detection(self) -> ObjectDetection | None:
        if self.disposition is not ObservationDisposition.VALID or self.distance_cm is None:
            return None
        return ObjectDetection(
            label="marker_1",
            position=self.position,
            distance_cm=self.distance_cm,
            distance_visual_cm=self.distance_cm,
            confidence=self.confidence,
            bbox_px=self.bbox_px,
        )


class MarkerDetectorBackend(Protocol):
    def detectMarkers(self, image: object) -> tuple[object, object, object]: ...


class OpenCVMarkerDetector(Detector[ArucoFrameDetection]):
    """Detect one configured ArUco ID from RGB frames."""

    def __init__(
        self,
        identity: MarkerIdentity,
        *,
        focal_px: float,
        aruco_api: object | None = None,
        oriented_frame_size_px: tuple[int, int] | None = None,
    ) -> None:
        if identity.family != "aruco":
            raise ValueError("The configured marker family is not ArUco")
        if not isfinite(focal_px) or focal_px <= 0:
            raise ValueError("Camera focal length must be finite and positive")
        if (not identity.identifier.isascii() or not identity.identifier.isdigit()
                or str(int(identity.identifier)) != identity.identifier):
            raise ValueError("ArUco identifier must be a canonical non-negative integer")
        if aruco_api is None:
            aruco_api = self._load_aruco_api()
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
        self.focal_px = float(focal_px)
        self.oriented_frame_size_px = (
            oriented_frame_size_px or load_runtime_settings().camera_oriented_frame_size_px
        )
        self._detector: MarkerDetectorBackend = detector

    @staticmethod
    def _load_aruco_api() -> object | None:
        import cv2

        return getattr(cv2, "aruco", None)

    def detect(self, frame_rgb: NDArray[np.uint8]) -> ArucoFrameDetection:
        grayscale = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
        corners_raw, ids_raw, _ = self._detector.detectMarkers(grayscale)
        corners = self._as_python_values(corners_raw)
        marker_ids = self._flatten_ids(ids_raw)
        if marker_ids is None:
            logger.warning("Détection ArUco non valide : malformed_marker_ids")
            return ArucoFrameDetection(
                ObservationDisposition.FAULT, reason="malformed_marker_ids",
            )
        if not marker_ids:
            if corners not in (None, []):
                logger.warning("Détection ArUco non valide : corners_without_marker_ids")
                return ArucoFrameDetection(
                    ObservationDisposition.FAULT, reason="corners_without_marker_ids",
                )
            return ArucoFrameDetection(ObservationDisposition.ABSENT)
        if not isinstance(corners, list) or len(corners) != len(marker_ids):
            logger.warning("Détection ArUco non valide : marker_id_corner_count_mismatch")
            return ArucoFrameDetection(
                ObservationDisposition.FAULT, reason="marker_id_corner_count_mismatch",
            )
        matches = [index for index, marker_id in enumerate(marker_ids) if marker_id == self.expected_id]
        if not matches:
            return ArucoFrameDetection(ObservationDisposition.ABSENT)
        if len(matches) > 1:
            return ArucoFrameDetection(
                ObservationDisposition.AMBIGUOUS, identity=self.identity,
                reason="multiple_configured_markers",
            )
        parsed_corners = self._parse_corners(corners[matches[0]])
        if parsed_corners is None:
            logger.warning("Détection ArUco non valide : malformed_marker_corners")
            return ArucoFrameDetection(
                ObservationDisposition.REJECTED, identity=self.identity,
                reason="malformed_marker_corners",
            )
        distance = estimate_marker_distance_cm(
            parsed_corners,
            self.focal_px,
            (frame_rgb.shape[1], frame_rgb.shape[0]),
            self.oriented_frame_size_px,
        )
        center_x = sum(x for x, _ in parsed_corners) / 4
        frame_width = frame_rgb.shape[1]
        position = (
            "left" if center_x < frame_width * 3 / 8
            else "right" if center_x > frame_width * 5 / 8
            else "center"
        )
        left = round(min(x for x, _ in parsed_corners))
        top = round(min(y for _, y in parsed_corners))
        right = round(max(x for x, _ in parsed_corners))
        bottom = round(max(y for _, y in parsed_corners))
        if distance is None:
            logger.warning("Pose ArUco inexploitable ; distance indisponible.")
        return ArucoFrameDetection(
            ObservationDisposition.VALID,
            identity=self.identity,
            corners_px=parsed_corners,
            distance_cm=distance,
            position=position,
            bbox_px=(left, top, right - left, bottom - top),
            confidence=1.0,
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
            if (isinstance(x, bool) or not isinstance(x, (int, float))
                    or isinstance(y, bool) or not isinstance(y, (int, float))
                    or not isfinite(x) or not isfinite(y)):
                return None
            parsed.append((float(x), float(y)))
        return tuple(parsed)
