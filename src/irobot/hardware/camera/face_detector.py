"""YuNet face detection on already enhanced RGB frames; no identity recognition."""

from dataclasses import replace
import logging
import math
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from irobot.config.settings import RuntimeSettings
from irobot.hardware.camera.distance_estimator import estimate_distance_cm
from irobot.interfaces.perception_pipeline import ObjectDetection

logger = logging.getLogger(__name__)


class FaceDetector:
    def __init__(self, settings: RuntimeSettings, *, focal_px: float | None = None) -> None:
        self._settings = settings
        self._focal_px = settings.camera_focal_px if focal_px is None else focal_px
        if not math.isfinite(self._focal_px) or self._focal_px <= 0:
            raise ValueError("Face focal_px must be finite and positive")
        model = Path(settings.camera_face_model_path)
        if not model.is_file():
            raise FileNotFoundError(f"Modèle YuNet introuvable : {model}")
        self._net = cv2.FaceDetectorYN.create(
            str(model), "", (300, 300),
            score_threshold=settings.camera_face_score_threshold,
            nms_threshold=0.3, top_k=5000,
        )
        self._last_detection: ObjectDetection | None = None
        self._lost_frames = 0
        self._frame_size: tuple[int, int] | None = None
        self._bounding_box: tuple[float, float, float, float] | None = None

    @property
    def bounding_box(self) -> tuple[float, float, float, float] | None:
        return self._bounding_box

    @property
    def is_cached(self) -> bool:
        return self._last_detection is not None and self._lost_frames > 0

    def reset(self) -> None:
        self._last_detection = None
        self._lost_frames = 0
        self._frame_size = None
        self._bounding_box = None

    def detect(self, frame_rgb: NDArray[np.uint8]) -> ObjectDetection | None:
        size = (frame_rgb.shape[1], frame_rgb.shape[0])
        if size != self._frame_size:
            self.reset()
            self._frame_size = size
        try:
            self._net.setInputSize(size)
            _, faces = self._net.detect(cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))
            detection = self._select_face(faces, size)
        except (cv2.error, ValueError):
            self.reset()
            logger.exception("Échec de la détection YuNet ; mémoire du visage effacée.")
            raise
        if detection is not None:
            self._last_detection = detection
            self._lost_frames = 0
            return replace(detection)
        if self._last_detection is not None and self._lost_frames < self._settings.camera_face_grace_frames:
            self._lost_frames += 1
            logger.debug("Visage mémorisé : image perdue %d/%d.", self._lost_frames,
                         self._settings.camera_face_grace_frames)
            return replace(self._last_detection)
        self._last_detection = None
        self._bounding_box = None
        return None

    def _select_face(
        self, faces: NDArray[np.float32] | None, size: tuple[int, int],
    ) -> ObjectDetection | None:
        if faces is None or faces.size == 0:
            return None
        if faces.ndim != 2 or faces.shape[1] != 15 or not np.isfinite(faces).all():
            raise ValueError("YuNet must return finite rows of 15 values")
        best = None
        for face in faces:
            x, y, width, height = map(float, face[:4])
            confidence = float(face[-1])
            if width <= 0 or height <= 0 or not 0 <= confidence <= 1:
                raise ValueError("YuNet returned invalid face geometry or confidence")
            if confidence < float(np.float32(self._settings.camera_face_score_threshold)):
                continue
            if x + width <= 0 or y + height <= 0 or x >= size[0] or y >= size[1]:
                logger.warning("Visage YuNet hors image ignoré.")
                continue
            if best is None or width > float(best[2]):
                best = face
        if best is None:
            return None
        x, _, width, _ = map(float, best[:4])
        distance = estimate_distance_cm(width, self._settings.camera_face_width_cm, self._focal_px)
        if distance is None or not math.isfinite(distance):
            raise ValueError("Distance visage inexploitable")
        self._bounding_box = (float(best[0]), float(best[1]), width, float(best[3]))
        center_x = (x + width / 2) * 480 / size[0]
        position = "left" if center_x < 180 else "right" if center_x > 300 else "center"
        return ObjectDetection(
            label="face", position=position, distance_cm=distance,
            distance_visual_cm=distance, confidence=float(best[-1]), diameter_px=width,
        )
