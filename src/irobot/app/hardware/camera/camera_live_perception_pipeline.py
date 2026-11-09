from __future__ import annotations

import dataclasses
import logging
import threading

import cv2
import numpy as np
from numpy.typing import NDArray

try:
    from picamera2 import Picamera2
except ModuleNotFoundError:  # pragma: no cover - non-Raspberry environments
    Picamera2 = None
from irobot.app.config.settings import load_runtime_settings
from irobot.app.domain.perception import PerceptionTarget
from irobot.app.hardware.camera.detector.target_detector import CameraTargetDetector
from irobot.app.hardware.camera.frame_enhancer import (
    FrameEnhancer,
    configure_exposure,
)
from irobot.app.interfaces.perception_contracts import (
    ObjectDetection,
    ObjectPerceptionPipeline,
    TargetFrameDetector,
)

logger = logging.getLogger(__name__)


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


class CameraLivePerceptionPipeline(ObjectPerceptionPipeline):
    """Perception Picamera2 : balles, ArUco (marker/tag) et YuNet (face/moi/humain).

    L'identité du marqueur configurée est utilisée, sinon aruco/DICT_4X4_50/1.
    La distance est estimée par pose pour un carré de 8 cm, avec la focale
    configurée et sans correction de distorsion.
    Les seuils horizontaux sont rapportés à une largeur de 480 px.
    """

    TARGET_FRAME_TIMEOUT_S = 1.0

    def __init__(
        self,
        *,
        camera_index: int = 0,
        poll_interval_s: float = 0.05,
        ball_diameter_cm: float | None = None,
        focal_px: float | None = None,
        smoothing_alpha: float = 0.4,
        detector: TargetFrameDetector | None = None,
        sensor: object | None = None,
        autostart: bool = True,
    ) -> None:
        self.camera_index = int(camera_index)
        self.sensor = sensor
        self.poll_interval_s = max(0.0, float(poll_interval_s))

        settings = load_runtime_settings()
        self._settings = settings
        self.ball_diameter_cm = float(settings.camera_ball_diameter_cm if ball_diameter_cm is None else ball_diameter_cm)
        self.focal_px = float(settings.camera_focal_px if focal_px is None else focal_px)
        self._detector = detector or CameraTargetDetector(
            settings,
            ball_diameter_cm=self.ball_diameter_cm,
            focal_px=self.focal_px,
        )
        self._frame_enhancer = FrameEnhancer(settings)
        self._distance_smoother = ExponentialSmoother(smoothing_alpha)
        self._active_target: PerceptionTarget | None = None
        self._last_detection: ObjectDetection | None = None
        # Dernière observation positive pas encore livrée : évite de la perdre si l'image suivante est vide.
        self._pending_detection: ObjectDetection | None = None
        self._requested_target: PerceptionTarget | None = None
        self._lock = threading.Lock()
        self._frame_condition = threading.Condition(self._lock)
        self._target_revision = 0
        self._frame_revision = -1
        self._frame_sequence = 0
        self._delivered_frame_sequence = -1
        self._capture_finished = False
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._capture_loop, name="camera-live-perception", daemon=False)
        if autostart:
            self._thread.start()

    def _process_frame(
        self,
        frame_rgb: NDArray[np.uint8],
        *,
        target: PerceptionTarget,
    ) -> ObjectDetection | None:
        if target is not self._active_target:
            if self._active_target is not None:
                self._detector.reset(self._active_target)
            self._detector.reset(target)
            self._active_target = target

        enhanced = self._frame_enhancer.apply(frame_rgb)
        detection = self._detector.detect(enhanced, target)
        if detection is None:
            self._distance_smoother.reset()
            return None

        distance = self._distance_smoother.update(
            detection.distance_visual_cm
            if detection.distance_visual_cm is not None
            else detection.distance_cm,
        )
        return dataclasses.replace(
            detection,
            distance_visual_cm=distance,
            distance_cm=distance,
        )

    def _capture_loop(self) -> None:
        if Picamera2 is None:
            logger.error("Perception caméra indisponible : Picamera2 absent.")
            with self._frame_condition:
                self._capture_finished = True
                self._frame_condition.notify_all()
            return

        camera = None
        try:
            camera = Picamera2(self.camera_index)
            # Picamera2 BGR888 fournit des octets R, G, B à _process_frame.
            config = camera.create_preview_configuration(
                main={"size": self._settings.camera_capture_size_px, "format": "BGR888"},
            )
            camera.configure(config)
            configure_exposure(camera, self._settings)
            camera.start()
            processed_revision = -1

            while not self._stop_event.is_set():
                with self._lock:
                    target = self._requested_target
                    revision = self._target_revision
                frame_rgb = camera.capture_array()
                if revision != processed_revision:
                    if self._active_target is not None:
                        self._detector.reset(self._active_target)
                    self._active_target = None
                    self._distance_smoother.reset()
                    processed_revision = revision
                rotated_frame_rgb = cv2.rotate(frame_rgb, cv2.ROTATE_90_CLOCKWISE)
                detection = (
                    self._process_frame(rotated_frame_rgb, target=target)
                    if target is not None
                    else None
                )
                with self._frame_condition:
                    # Une image en vol ne doit pas satisfaire une nouvelle demande de cible.
                    if revision == self._target_revision:
                        self._last_detection = detection
                        if detection is not None:
                            self._pending_detection = detection
                        self._frame_revision = revision
                        self._frame_sequence += 1
                    self._frame_condition.notify_all()

                if self.poll_interval_s > 0.0:
                    self._stop_event.wait(self.poll_interval_s)
        except Exception:
            logger.exception("Échec de la capture caméra.")
            with self._frame_condition:
                self._last_detection = None
                self._frame_revision = -1
        finally:
            with self._frame_condition:
                self._capture_finished = True
                self._frame_condition.notify_all()
            if camera is not None:
                try:
                    camera.stop()
                except Exception:
                    logger.exception("Échec de l'arrêt de la caméra.")
                try:
                    camera.close()
                except Exception:
                    logger.exception("Échec de la fermeture de la caméra.")

    def set_face_target(self, name: str | None, embedding: NDArray[np.float32] | None = None) -> None:
        """Restreint la détection de visage à une personne connue (`None` : tout visage)."""
        setter = getattr(self._detector, "set_face_target", None)
        if setter is None:
            raise RuntimeError("Le détecteur de la caméra ne gère pas la reconnaissance de visage.")
        setter(name, embedding)

    def release_target(self) -> None:
        """Arrête la détection live : le thread caméra cesse d'analyser les images."""
        with self._frame_condition:
            self._target_revision += 1
            self._requested_target = None
            self._last_detection = None
            self._pending_detection = None

    def detect(self, *, target: PerceptionTarget) -> ObjectDetection | None:
        with self._frame_condition:
            if target is not self._requested_target:
                self._target_revision += 1
                self._last_detection = None
                self._pending_detection = None
            self._requested_target = target
            revision = self._target_revision
            if self._thread.is_alive():
                ready = self._frame_condition.wait_for(
                    lambda: self._frame_revision == revision
                    or self._stop_event.is_set()
                    or self._capture_finished,
                    timeout=self.TARGET_FRAME_TIMEOUT_S,
                )
                if not ready:
                    logger.error(
                        "Délai dépassé en attendant une image caméra pour la cible %s.",
                        target.value,
                    )
                    return None
                if self._frame_revision != revision:
                    return None
            detection = self._last_detection or self._pending_detection
            self._pending_detection = None
            repeated_frame = self._frame_sequence == self._delivered_frame_sequence
            self._delivered_frame_sequence = self._frame_sequence

        if detection is None:
            return None
        return dataclasses.replace(detection, cached=detection.cached or repeated_frame)

    def close(self, timeout_s: float | None = None) -> None:
        with self._frame_condition:
            self._stop_event.set()
            self._frame_condition.notify_all()
        if self._thread.is_alive():
            self._thread.join(timeout=None if timeout_s is None else max(0.0, float(timeout_s)))
            if self._thread.is_alive():
                raise TimeoutError("Le thread caméra n'est pas arrêté.")
