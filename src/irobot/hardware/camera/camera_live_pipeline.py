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
from irobot.hardware.camera.color_detector import choose_best_result_with_metrics, detect_colored_objects
from irobot.hardware.camera.distance_estimator import (
    DistanceReader,
    ExponentialSmoother,
    estimate_distance_cm,
    fuse_with_ultrasound,
)
from irobot.interfaces.perception_pipeline import ObjectDetection, ObjectPerceptionPipeline

logger = logging.getLogger(__name__)


class CameraLivePerceptionPipeline(ObjectPerceptionPipeline):
    """Pipeline de perception live basé sur Picamera2 + détection couleur."""

    def __init__(
        self,
        *,
        camera_index: int = 0,
        default_target: str = "red",
        poll_interval_s: float = 0.05,
        ball_diameter_cm: float | None = None,
        focal_px: float | None = None,
        smoothing_alpha: float = 0.4,
        distance_reader: DistanceReader | None = None,
        fusion_enabled: bool | None = None,
        fusion_tolerance: float = 0.25,
        autostart: bool = True,
    ) -> None:
        self.camera_index = int(camera_index)
        self.default_target = (default_target or "red").strip().lower()
        self.poll_interval_s = max(0.0, float(poll_interval_s))

        settings = load_runtime_settings()
        self.ball_diameter_cm = float(settings.camera_ball_diameter_cm if ball_diameter_cm is None else ball_diameter_cm)
        self.focal_px = float(settings.camera_focal_px if focal_px is None else focal_px)
        self.distance_reader = distance_reader
        self.fusion_enabled = bool(settings.camera_ultrasonic_fusion if fusion_enabled is None else fusion_enabled)
        self.fusion_tolerance = float(fusion_tolerance)
        self._smoother = ExponentialSmoother(smoothing_alpha)

        self._last_detection: ObjectDetection | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._capture_loop, name="camera-live-perception", daemon=False)
        if autostart:
            self._thread.start()

    @staticmethod
    def _result_position_to_pipeline_position(result_position: str) -> str:
        value = (result_position or "").upper()
        if "A_GAUCHE" in value:
            return "left"
        if "A_DROITE" in value:
            return "right"
        if "CENTRE" in value or "EN_HAUT" in value or "EN_BAS" in value:
            return "center"
        return "UNKNOWN"

    @staticmethod
    def _result_to_detection(result: str, diameter_px: float | None = None) -> ObjectDetection | None:
        if not result or result == "NONE":
            return None

        parts = result.split("_", 2)
        if len(parts) < 3:
            return None

        kind, color, position_raw = parts
        label = f"{color.lower()}_{kind.lower()}"
        position = CameraLivePerceptionPipeline._result_position_to_pipeline_position(position_raw)
        confidence = 0.95 if kind == "BALL" else 0.75
        return ObjectDetection(
            label=label, position=position, distance_cm=None, confidence=confidence, diameter_px=diameter_px
        )

    def _compute_visual_distance_cm(self, detection: ObjectDetection) -> float | None:
        """Estimation visuelle lissée (thread caméra) ; aucune lecture capteur ici."""
        visual = None
        if detection.label.endswith("_ball"):
            visual = estimate_distance_cm(detection.diameter_px, self.ball_diameter_cm, self.focal_px)
        return self._smoother.update(visual)

    def _fuse_distance_cm(self, detection: ObjectDetection) -> float | None:
        """Fusion ultrason, appelée depuis le thread appelant de detect()."""
        visual = detection.distance_visual_cm
        if visual is None or not self.fusion_enabled or self.distance_reader is None:
            return visual
        if detection.position != "center":
            return visual
        try:
            ultrasound = self.distance_reader()
        except Exception:
            return visual
        return fuse_with_ultrasound(visual, ultrasound, self.fusion_tolerance)

    def _process_frame(self, frame_rgb) -> ObjectDetection | None:
        """Détecte la meilleure cible dans une frame déjà orientée (RGB) et renseigne la distance."""
        results: list[str] = []
        metrics_by_result: dict[str, dict | None] = {}
        for color in self._iter_colors_for_target(None, self.default_target):
            candidates = detect_colored_objects(frame_rgb, color_name=color, is_rgb=True, debug=False)
            best, metrics = choose_best_result_with_metrics(candidates, color, frame_rgb.shape, robotic=True)
            if best:
                results.append(best)
                metrics_by_result.setdefault(best, metrics)

        chosen = self._select_robotic_result(results) or ""
        metrics = metrics_by_result.get(chosen)
        detection = self._result_to_detection(chosen, metrics["diameter_px"] if metrics else None)
        if detection is None:
            self._smoother.reset()
            return None
        detection.distance_visual_cm = self._compute_visual_distance_cm(detection)
        detection.distance_cm = detection.distance_visual_cm
        return detection

    @staticmethod
    def _select_robotic_result(results: list[str]) -> str | None:
        if not results:
            return None
        for item in results:
            if item.startswith("BALL_"):
                return item
        for item in results:
            if item.startswith("OBJECT_"):
                return item
        return results[0]

    @staticmethod
    def _iter_colors_for_target(target: str | None, default_target: str) -> list[str]:
        desired = (target or default_target or "both").strip().lower()
        if desired == "both":
            return ["red", "yellow"]
        if "yellow" in desired:
            return ["yellow", "red"]
        return ["red", "yellow"]

    def _capture_loop(self) -> None:
        if Picamera2 is None:
            return

        camera = None
        try:
            camera = Picamera2(self.camera_index)
            # Picamera2 BGR888 fournit des octets R, G, B à _process_frame.
            config = camera.create_preview_configuration(
                main={"size": (640, 480), "format": "BGR888"}
            )
            camera.configure(config)
            camera.start()

            while not self._stop_event.is_set():
                frame_rgb = camera.capture_array()
                rotated_frame_rgb = cv2.rotate(frame_rgb, cv2.ROTATE_90_CLOCKWISE)
                detection = self._process_frame(rotated_frame_rgb)
                with self._lock:
                    self._last_detection = detection

                if self.poll_interval_s > 0.0:
                    self._stop_event.wait(self.poll_interval_s)
        except Exception:
            logger.exception("Échec de la capture caméra.")
            with self._lock:
                self._last_detection = None
        finally:
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
        with self._lock:
            detection = self._last_detection

        if detection is None:
            return None
        if target:
            expected = target.strip().lower()
            label = detection.label.lower()
            if expected not in label and label not in expected:
                return None
        return dataclasses.replace(detection, distance_cm=self._fuse_distance_cm(detection))

    def close(self, timeout_s: float | None = None) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=None if timeout_s is None else max(0.0, float(timeout_s)))
            if self._thread.is_alive():
                raise TimeoutError("Le thread caméra n'est pas arrêté.")
