"""Camera detector implementations and shared types."""

from .aruco_detector import (
    MARKER_SIDE_CM,
    ArucoFrameDetection,
    MarkerDetectorBackend,
    ObservationDisposition,
    OpenCVMarkerDetector,
    estimate_marker_distance_cm,
)
from .base_detector import Detector
from .color_detector import ColorDetector
from .face_detector import FaceDetector
from .face_gallery import FaceGallery

__all__ = [
    "MARKER_SIDE_CM",
    "ArucoFrameDetection",
    "ColorDetector",
    "Detector",
    "FaceDetector",
    "FaceGallery",
    "MarkerDetectorBackend",
    "ObservationDisposition",
    "OpenCVMarkerDetector",
    "estimate_marker_distance_cm",
]
