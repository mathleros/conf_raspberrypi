from __future__ import annotations

import dataclasses
import logging
import threading

import cv2

try:
    from picamera2 import Picamera2
except ModuleNotFoundError:  # pragma: no cover - non-Raspberry environments
    Picamera2 = None

from irobot.config.settings import load_runtime_settings
from irobot.hardware.camera.frame_enhancer import configure_exposure
from irobot.hardware.camera.frame_processor import CameraFrameProcessor
from irobot.interfaces.perception_contracts import ObjectDetection, ObjectPerceptionPipeline

logger = logging.getLogger(__name__)


class CameraLivePerceptionPipeline(ObjectPerceptionPipeline):
    """Perception Picamera2 : balles, ArUco (marker/me) et YuNet (face/human).

    Sans filtre balle, ArUco est prioritaire. L'identité configurée est utilisée,
    sinon aruco/DICT_4X4_50/1 ; distance directe indicative estimée par pose
    pour un carré de 8 cm, avec la focale configurée et sans correction de distorsion.
    Les seuils horizontaux sont rapportés à une largeur de 480 px.
    """

    TARGET_FRAME_TIMEOUT_S = 1.0

    def __init__(
        self,
        *,
        camera_index: int = 0,
        default_target: str = "red",
        poll_interval_s: float = 0.05,
        ball_diameter_cm: float | None = None,
        focal_px: float | None = None,
        smoothing_alpha: float = 0.4,
        sensor: object | None = None,
        autostart: bool = True,
    ) -> None:
        self.camera_index = int(camera_index)
        self.sensor = sensor
        self.default_target = (default_target or "").strip().lower()
        if self.default_target == "human":
            self.default_target = "face"
        self.poll_interval_s = max(0.0, float(poll_interval_s))

        settings = load_runtime_settings()
        self._settings = settings
        self.ball_diameter_cm = float(settings.camera_ball_diameter_cm if ball_diameter_cm is None else ball_diameter_cm)
        self.focal_px = float(settings.camera_focal_px if focal_px is None else focal_px)
        self._frame_processor = CameraFrameProcessor(
            settings,
            ball_diameter_cm=self.ball_diameter_cm,
            focal_px=self.focal_px,
            smoothing_alpha=smoothing_alpha,
        )
        self._last_detection: ObjectDetection | None = None
        self._requested_target: str | None = None
        self._lock = threading.Lock()
        self._frame_condition = threading.Condition(self._lock)
        self._target_revision = 0
        self._frame_revision = -1
        self._capture_finished = False
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._capture_loop, name="camera-live-perception", daemon=False)
        if autostart:
            self._thread.start()

    def _process_frame(self, frame_rgb, *, target: str | None = None) -> ObjectDetection | None:
        """Traite une image RGB via le composant dédié au routage des détecteurs."""
        if target is None:
            with self._lock:
                target = self._requested_target or self.default_target
        return self._frame_processor.process_frame(
            frame_rgb,
            target=target,
            default_target=self.default_target,
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
                main={"size": self._settings.camera_capture_size_px, "format": "BGR888"}
            )
            camera.configure(config)
            configure_exposure(camera, self._settings)
            camera.start()
            processed_revision = -1

            while not self._stop_event.is_set():
                with self._lock:
                    target = self._requested_target or self.default_target
                    revision = self._target_revision
                frame_rgb = camera.capture_array()
                if revision != processed_revision:
                    self._frame_processor.reset_for_target_change()
                    processed_revision = revision
                rotated_frame_rgb = cv2.rotate(frame_rgb, cv2.ROTATE_90_CLOCKWISE)
                detection = self._process_frame(rotated_frame_rgb, target=target)
                with self._frame_condition:
                    # Une image en vol ne doit pas satisfaire une nouvelle demande de cible.
                    if revision == self._target_revision:
                        self._last_detection = detection
                        self._frame_revision = revision
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

    def detect(self, *, target: str | None = None) -> ObjectDetection | None:
        expected = (target or "").strip().lower()
        if expected == "human":
            expected = "face"
        requested = "marker" if expected == "me" else expected
        with self._frame_condition:
            previous = self._requested_target or self.default_target
            previous = "marker" if previous == "me" else previous
            desired = requested or self.default_target
            desired = "marker" if desired == "me" else desired
            if desired != previous:
                self._target_revision += 1
                self._last_detection = None
            self._requested_target = requested or None
            revision = self._target_revision
            if self._thread.is_alive():
                ready = self._frame_condition.wait_for(
                    lambda: self._frame_revision == revision
                    or self._stop_event.is_set()
                    or self._capture_finished,
                    timeout=self.TARGET_FRAME_TIMEOUT_S,
                )
                if not ready:
                    logger.error("Délai dépassé en attendant une image caméra pour la cible %r.", target)
                    return None
                if self._frame_revision != revision:
                    return None
            detection = self._last_detection

        if detection is None:
            return None
        if expected:
            label = detection.label.lower()
            if expected in {"marker", "me"}:
                if label != "marker_1":
                    return None
            elif expected not in label and label not in expected:
                return None
        return dataclasses.replace(detection)

    def close(self, timeout_s: float | None = None) -> None:
        with self._frame_condition:
            self._stop_event.set()
            self._frame_condition.notify_all()
        if self._thread.is_alive():
            self._thread.join(timeout=None if timeout_s is None else max(0.0, float(timeout_s)))
            if self._thread.is_alive():
                raise TimeoutError("Le thread caméra n'est pas arrêté.")
