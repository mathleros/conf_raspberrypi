from __future__ import annotations

import threading
import time

import cv2

try:
    from picamera2 import Picamera2
except ModuleNotFoundError:  # pragma: no cover - non-Raspberry environments
    Picamera2 = None

from irobot.hardware.camera.color_detector import choose_best_result, detect_colored_objects
from irobot.interfaces.perception_pipeline import ObjectDetection, ObjectPerceptionPipeline


class CameraLivePerceptionPipeline(ObjectPerceptionPipeline):
    """Pipeline de perception live basé sur Picamera2 + détection couleur."""

    def __init__(
        self,
        *,
        camera_index: int = 0,
        default_target: str = "red",
        poll_interval_s: float = 0.05,
    ) -> None:
        self.camera_index = int(camera_index)
        self.default_target = (default_target or "red").strip().lower()
        self.poll_interval_s = max(0.0, float(poll_interval_s))

        self._last_detection: ObjectDetection | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._capture_loop, name="camera-live-perception", daemon=True)
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
    def _result_to_detection(result: str) -> ObjectDetection | None:
        if not result or result == "NONE":
            return None

        parts = result.split("_", 2)
        if len(parts) < 3:
            return None

        kind, color, position_raw = parts
        label = f"{color.lower()}_{kind.lower()}"
        position = CameraLivePerceptionPipeline._result_position_to_pipeline_position(position_raw)
        confidence = 0.95 if kind == "BALL" else 0.75
        return ObjectDetection(label=label, position=position, distance_cm=None, confidence=confidence)

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
            # Configuration matérielle explicite en basse résolution 640x480 RGB
            config = camera.create_preview_configuration(
                main={"size": (640, 480), "format": "RGB888"}
            )
            camera.configure(config)
            camera.start()

            while not self._stop_event.is_set():
                frame_rgb = camera.capture_array()
                rotated_frame_rgb = cv2.rotate(frame_rgb, cv2.ROTATE_90_CLOCKWISE)
                
                results: list[str] = []
                for color in self._iter_colors_for_target(None, self.default_target):
                    candidates = detect_colored_objects(rotated_frame_rgb, color_name=color, is_rgb=True, debug=False)
                    best = choose_best_result(candidates, color, rotated_frame_rgb.shape, robotic=True)
                    if best:
                        results.append(best)

                detection = self._result_to_detection(self._select_robotic_result(results) or "")
                with self._lock:
                    self._last_detection = detection

                if self.poll_interval_s > 0.0:
                    time.sleep(self.poll_interval_s)
        except Exception:
            with self._lock:
                self._last_detection = None
        finally:
            if camera is not None:
                try:
                    camera.stop()
                except Exception:
                    pass

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
        return detection

    def close(self, timeout_s: float = 0.5) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=max(0.0, float(timeout_s)))
