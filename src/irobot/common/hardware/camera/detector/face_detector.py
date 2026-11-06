"""YuNet face detection on already enhanced RGB frames; optional SFace identity filter."""

import logging
import math
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from irobot.common.config.settings import RuntimeSettings
from irobot.common.interfaces.perception_contracts import ObjectDetection

from .base_detector import Detector
from .distance_estimator import estimate_distance_cm
from .face_gallery import FaceEmbedder, FaceGallery

logger = logging.getLogger(__name__)

_POSITION_REFERENCE_WIDTH = 480
_POSITION_LEFT_MAX = 160
_POSITION_RIGHT_MIN = 320
_TRACK_IOU_MIN = 0.3


class FaceDetector(Detector[ObjectDetection]):
    def __init__(
        self, settings: RuntimeSettings, *, focal_px: float | None = None,
        gallery: FaceGallery | None = None,
    ) -> None:
        self._settings = settings
        self._gallery = gallery
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
        self._embedder: FaceEmbedder | None = None
        self._target_name: str | None = None
        self._target_embedding: NDArray[np.float32] | None = None
        self._pending_target: tuple[str | None, NDArray[np.float32] | None] | None = None
        self._tracked_box: tuple[float, float, float, float] | None = None
        self._frames_since_recognition = 0

    def set_target(self, name: str | None, embedding: NDArray[np.float32] | None = None) -> None:
        """Suit uniquement la personne `name` ; `None` rétablit le suivi du plus grand visage."""
        if (name is None) != (embedding is None):
            raise ValueError("Face target needs both a name and an embedding, or neither")
        self._pending_target = (name, embedding)

    def _apply_pending_target(self) -> None:
        if self._pending_target is None:
            return
        self._target_name, self._target_embedding = self._pending_target
        self._pending_target = None
        if self._target_embedding is not None and self._embedder is None:
            self._embedder = FaceEmbedder(self._settings)
        self.reset()

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
        self._tracked_box = None
        self._frames_since_recognition = 0

    def detect(self, frame_rgb: NDArray[np.uint8]) -> ObjectDetection | None:
        self._apply_pending_target()
        size = (frame_rgb.shape[1], frame_rgb.shape[0])
        if size != self._frame_size:
            self.reset()
            self._frame_size = size
        try:
            self._net.setInputSize(size)
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            _, faces = self._net.detect(frame_bgr)
            detection = self._select_face(faces, size, frame_bgr)
        except (cv2.error, ValueError):
            self.reset()
            logger.exception("Échec de la détection ou reconnaissance du visage ; mémoire du visage effacée.")
            raise
        if detection is not None:
            logger.info(
                "Visage détecté : position=%s, distance=%.1f cm, confiance=%.2f, bbox=%s",
                detection.position, detection.distance_cm, detection.confidence, detection.bbox_px,
            )
            self._last_detection = detection
            self._lost_frames = 0
            return replace(detection)
        if self._last_detection is not None and self._lost_frames < self._settings.camera_face_grace_frames:
            self._lost_frames += 1
            logger.debug("Visage mémorisé : image perdue %d/%d.", self._lost_frames,
                         self._settings.camera_face_grace_frames)
            return replace(self._last_detection, cached=True)
        if self._last_detection is not None:
            logger.info("Visage perdu : délai de grâce épuisé (%d images).",
                        self._settings.camera_face_grace_frames)
        self._last_detection = None
        self._bounding_box = None
        return None

    def _select_face(
        self, faces: NDArray[np.float32] | None, size: tuple[int, int],
        frame_bgr: NDArray[np.uint8] | None = None,
    ) -> ObjectDetection | None:
        if faces is None or faces.size == 0:
            return None
        self._validate_faces(faces)
        if self._target_embedding is not None and frame_bgr is not None:
            best = self._pick_target_face(faces, size, frame_bgr)
        else:
            best = self._pick_largest_face(faces, size)
        if best is None:
            return None
        identity = self._target_name
        if identity is None and self._gallery is not None and frame_bgr is not None:
            identity = self._gallery.identify(frame_bgr, best)
        return replace(self._build_detection(best, size), identity=identity)

    @staticmethod
    def _validate_faces(faces: NDArray[np.float32]) -> None:
        if faces.ndim != 2 or faces.shape[1] != 15 or not np.isfinite(faces).all():
            raise ValueError("YuNet must return finite rows of 15 values")
        if (faces[:, 2] <= 0).any() or (faces[:, 3] <= 0).any() or ((faces[:, -1] < 0) | (faces[:, -1] > 1)).any():
            raise ValueError("YuNet returned invalid face geometry or confidence")

    def _pick_target_face(
        self, faces: NDArray[np.float32], size: tuple[int, int], frame_bgr: NDArray[np.uint8],
    ) -> NDArray[np.float32] | None:
        """Reconnaît la cible toutes les N images ; entre-temps, suit sa boîte par IoU."""
        candidates = self._eligible_faces(faces, size)
        if not candidates:
            self._tracked_box = None
            return None
        self._frames_since_recognition += 1
        if self._tracked_box is not None and self._frames_since_recognition < self._settings.camera_face_recognition_every_n:
            tracked = max(candidates, key=lambda face: _iou(tuple(map(float, face[:4])), self._tracked_box))
            if _iou(tuple(map(float, tracked[:4])), self._tracked_box) >= _TRACK_IOU_MIN:
                self._tracked_box = tuple(map(float, tracked[:4]))
                return tracked
        return self._recognize_target(candidates, frame_bgr)

    def _recognize_target(
        self, candidates: list[NDArray[np.float32]], frame_bgr: NDArray[np.uint8],
    ) -> NDArray[np.float32] | None:
        self._frames_since_recognition = 0
        best, best_score = None, -1.0
        for face in candidates:
            score = self._embedder.similarity(self._target_embedding, self._embedder.embed(frame_bgr, face))
            if score > best_score:
                best, best_score = face, score
        if best is None or not self._embedder.is_match(best_score):
            self._tracked_box = None
            return None
        self._tracked_box = tuple(map(float, best[:4]))
        return best

    def _eligible_faces(
        self, faces: NDArray[np.float32], size: tuple[int, int],
    ) -> list[NDArray[np.float32]]:
        threshold = float(np.float32(self._settings.camera_face_score_threshold))
        eligible = []
        for face in faces:
            x, y, width, height = map(float, face[:4])
            if float(face[-1]) < threshold:
                continue
            if x + width <= 0 or y + height <= 0 or x >= size[0] or y >= size[1]:
                logger.warning("Visage YuNet hors image ignoré.")
                continue
            eligible.append(face)
        return eligible

    def _pick_largest_face(
        self, faces: NDArray[np.float32], size: tuple[int, int],
    ) -> NDArray[np.float32] | None:
        best = None
        for face in self._eligible_faces(faces, size):
            if best is None or float(face[2]) > float(best[2]):
                best = face
        return best

    def _build_detection(self, best: NDArray[np.float32], size: tuple[int, int]) -> ObjectDetection:
        bounding_box = tuple(map(float, best[:4]))
        x, _, width, _ = bounding_box
        distance = estimate_distance_cm(width, self._settings.camera_face_width_cm, self._focal_px)
        if distance is None or not math.isfinite(distance):
            raise ValueError("Distance visage inexploitable")
        self._bounding_box = bounding_box
        center_x = (x + width / 2) * _POSITION_REFERENCE_WIDTH / size[0]
        half_width = _POSITION_REFERENCE_WIDTH / 2
        return ObjectDetection(
            label="face", position=_position_from_center_x(center_x),
            offset_x=(center_x - half_width) / half_width, distance_cm=distance,
            distance_visual_cm=distance, confidence=float(best[-1]), diameter_px=width,
            bbox_px=tuple(map(int, bounding_box)),
        )


def _position_from_center_x(center_x: float) -> str:
    if center_x < _POSITION_LEFT_MAX:
        return "left"
    return "right" if center_x > _POSITION_RIGHT_MIN else "center"


def _iou(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    inter_w = min(ax + aw, bx + bw) - max(ax, bx)
    inter_h = min(ay + ah, by + bh) - max(ay, by)
    if inter_w <= 0 or inter_h <= 0:
        return 0.0
    inter = inter_w * inter_h
    return inter / (aw * ah + bw * bh - inter)
