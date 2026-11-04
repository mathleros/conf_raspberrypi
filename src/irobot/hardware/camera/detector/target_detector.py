"""Dispatch camera frames to the detector for the requested target."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from irobot.config.settings import MarkerIdentity, RuntimeSettings
from irobot.domain.perception import PerceptionTarget
from irobot.hardware.camera.detector import ColorDetector, FaceDetector, OpenCVMarkerDetector
from irobot.interfaces.perception_contracts import ObjectDetection


class CameraTargetDetector:
    """Dispatch a frame to the detector for the requested semantic target."""

    def __init__(
        self,
        settings: RuntimeSettings,
        *,
        ball_diameter_cm: float,
        focal_px: float,
    ) -> None:
        red = ColorDetector("red", ball_diameter_cm, focal_px)
        yellow = ColorDetector("yellow", ball_diameter_cm, focal_px)
        self._color_detectors = {
            PerceptionTarget.RED_BALL: red,
            PerceptionTarget.YELLOW_BALL: yellow,
        }
        self._marker_detector = OpenCVMarkerDetector(
            settings.human_marker_identity
            or MarkerIdentity("aruco", "DICT_4X4_50", "1"),
            focal_px=focal_px,
            oriented_frame_size_px=settings.camera_oriented_frame_size_px,
        )
        self._settings = settings
        self._focal_px = focal_px
        self._face_detector: FaceDetector | None = None

    def detect(
        self,
        frame_rgb: NDArray[np.uint8],
        target: PerceptionTarget,
    ) -> ObjectDetection | None:
        if target in self._color_detectors:
            return self._color_detectors[target].detect(frame_rgb)
        if target is PerceptionTarget.ANY_BALL:
            return (
                self._color_detectors[PerceptionTarget.RED_BALL].detect(frame_rgb)
                or self._color_detectors[PerceptionTarget.YELLOW_BALL].detect(frame_rgb)
            )
        if target is PerceptionTarget.USER_MARKER:
            return self._marker_detector.detect(frame_rgb).as_object_detection()
        if target is PerceptionTarget.FACE:
            if self._face_detector is None:
                self._face_detector = FaceDetector(self._settings, focal_px=self._focal_px)
            return self._face_detector.detect(frame_rgb)
        raise ValueError(f"Unsupported perception target: {target!r}")

    def reset(self, target: PerceptionTarget) -> None:
        if target is PerceptionTarget.FACE and self._face_detector is not None:
            self._face_detector.reset()
