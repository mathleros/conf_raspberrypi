"""Camera detector implementations and shared types."""

from .color_detector import ColorDetector
from .detector import Detector
from .face_detector import FaceDetector
from .marker_detector import (
    ArucoFrameDetection,
    MarkerDetectorBackend,
    ObservationDisposition,
    OpenCVMarkerDetector,
)

__all__ = [
    "ArucoFrameDetection",
    "ColorDetector",
    "Detector",
    "FaceDetector",
    "MarkerDetectorBackend",
    "ObservationDisposition",
    "OpenCVMarkerDetector",
]
