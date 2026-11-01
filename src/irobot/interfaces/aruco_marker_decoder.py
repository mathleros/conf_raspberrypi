"""Decode a configured marker through an injected ArUco API, without camera access."""

from __future__ import annotations

from irobot.config.settings import MarkerIdentity
from irobot.interfaces.human_perception_contracts import (
    ArucoDetectorBackend, ArucoFrameDetection, ObservationDisposition, finite_number,
)


class OpenCVArucoMarkerDecoder:
    """Decode one configured ArUco ID; geometry/calibration remain separate."""

    def __init__(
        self, identity: MarkerIdentity, *, aruco_api: object | None = None,
    ) -> None:
        if identity.family != "aruco":
            raise ValueError("The configured marker family is not ArUco")
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
        self._detector: ArucoDetectorBackend = detector

    @staticmethod
    def _load_aruco_api() -> object | None:
        from irobot.hardware.camera.aruco_backend import load_aruco_api

        return load_aruco_api()

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
                ObservationDisposition.AMBIGUOUS, identity=self.identity,
                reason="multiple_configured_markers",
            )
        parsed_corners = self._parse_corners(corners[matches[0]])
        if parsed_corners is None:
            return ArucoFrameDetection(
                ObservationDisposition.REJECTED, identity=self.identity,
                reason="malformed_marker_corners",
            )
        return ArucoFrameDetection(
            ObservationDisposition.VALID, identity=self.identity, corners_px=parsed_corners,
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
            if not finite_number(x) or not finite_number(y):
                return None
            parsed.append((float(x), float(y)))
        return tuple(parsed)
