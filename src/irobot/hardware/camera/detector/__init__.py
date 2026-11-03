"""Camera detector implementations and shared types."""

from .color_detector import ColorDetector
from .detector import Detector
from .face_detector import FaceDetector
from .aruco_detector import (
    ArucoFrameDetection,
    MARKER_SIDE_CM,
    MarkerDetectorBackend,
    ObservationDisposition,
    OpenCVMarkerDetector,
    estimate_marker_distance_cm,
)

__all__ = [
    "ArucoFrameDetection",
    "ColorDetector",
    "Detector",
    "FaceDetector",
    "MARKER_SIDE_CM",
    "MarkerDetectorBackend",
    "ObservationDisposition",
    "OpenCVMarkerDetector",
    "estimate_marker_distance_cm",
]
