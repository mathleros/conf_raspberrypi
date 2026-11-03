"""Route enhanced camera frames to the appropriate object detector."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from irobot.config.settings import MarkerIdentity, RuntimeSettings
from irobot.hardware.camera.detector import (
    ColorDetector,
    FaceDetector,
    OpenCVMarkerDetector,
)
from irobot.hardware.camera.frame_enhancer import FrameEnhancer
from irobot.interfaces.perception_contracts import ObjectDetection


class ExponentialSmoother:
    """Filtre exponentiel : s = alpha * x + (1 - alpha) * s."""

    def __init__(self, alpha: float = 0.4) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha doit être dans ]0, 1]")
        self.alpha = float(alpha)
        self._value: float | None = None

    def update(self, measure: float | None) -> float | None:
        """Ajoute une mesure ; une mesure None réinitialise le filtre (cible perdue)."""
        if measure is None:
            self._value = None
            return None
        if self._value is None:
            self._value = float(measure)
        else:
            self._value = self.alpha * float(measure) + (1.0 - self.alpha) * self._value
        return self._value

    def reset(self) -> None:
        self._value = None


class CameraFrameProcessor:
    """Enhance each frame, select a detector and smooth ball distances."""

    def __init__(
        self,
        settings: RuntimeSettings,
        *,
        ball_diameter_cm: float,
        focal_px: float,
        smoothing_alpha: float,
    ) -> None:
        self._settings = settings
        self._focal_px = focal_px
        self._frame_enhancer = FrameEnhancer(settings)
        self._face_detector: FaceDetector | None = None
        self._color_detectors = {
            color: ColorDetector(color, ball_diameter_cm, focal_px)
            for color in ("red", "yellow")
        }
        self._marker_detector = OpenCVMarkerDetector(
            settings.human_marker_identity or MarkerIdentity("aruco", "DICT_4X4_50", "1"),
            focal_px=focal_px,
            oriented_frame_size_px=settings.camera_oriented_frame_size_px,
        )
        self._smoother = ExponentialSmoother(smoothing_alpha)

    def reset_for_target_change(self) -> None:
        if self._face_detector is not None:
            self._face_detector.reset()
        self._smoother.reset()

    def process_frame(
        self,
        frame_rgb: NDArray[np.uint8],
        *,
        target: str | None,
        default_target: str,
    ) -> ObjectDetection | None:
        frame_rgb = self._frame_enhancer.apply(frame_rgb)
        if target is None:
            target = default_target

        if target in {"face", "human"}:
            self._smoother.reset()
            if self._face_detector is None:
                self._face_detector = FaceDetector(self._settings, focal_px=self._focal_px)
            return self._face_detector.detect(frame_rgb)

        if self._face_detector is not None:
            self._face_detector.reset()

        marker_only = target in {"marker", "me"}
        ball_filter = target == "both" or any(
            value in target for value in ("red", "yellow", "ball")
        )
        if marker_only or not ball_filter:
            marker = self._marker_detector.detect(frame_rgb).as_object_detection()
            if marker is not None or marker_only:
                self._smoother.reset()
                return marker

        selected = self._detect_color(frame_rgb, target, default_target)
        if selected is None:
            self._smoother.reset()
            return None

        distance = self._smoother.update(selected.distance_visual_cm)
        selected.distance_visual_cm = distance
        selected.distance_cm = distance
        return selected

    def _detect_color(
        self,
        frame_rgb: NDArray[np.uint8],
        target: str,
        default_target: str,
    ) -> ObjectDetection | None:
        selected: ObjectDetection | None = None
        for color in self._iter_colors_for_target(target, default_target):
            detection = self._color_detectors[color].detect(frame_rgb)
            if detection is None:
                continue
            if selected is None or detection.label.endswith("_ball"):
                selected = detection
            if detection.label.endswith("_ball"):
                break
        return selected

    @staticmethod
    def _iter_colors_for_target(target: str | None, default_target: str) -> list[str]:
        desired = (target or default_target or "both").strip().lower()
        if desired == "both":
            return ["red", "yellow"]
        if "yellow" in desired:
            return ["yellow", "red"]
        return ["red", "yellow"]
