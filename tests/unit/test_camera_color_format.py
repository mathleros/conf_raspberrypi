import cv2
import numpy as np
import pytest

from irobot.hardware.camera import calibrate_distance
from irobot.hardware.camera import camera_live_pipeline


@pytest.fixture
def camera_factory():
    class Camera:
        def __init__(self, index):
            self.config = None
            self.stopped = False
            self.closed = False
            self.captures = 0
            self.on_capture = lambda: None

        def create_preview_configuration(self, **kwargs):
            return kwargs

        def configure(self, config):
            self.config = config

        def start(self):
            pass

        def capture_array(self):
            self.captures += 1
            if self.captures > 3:
                raise RuntimeError("La calibration ne détecte pas la cible synthétique rouge.")
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            # Ordre mémoire Picamera2 : BGR888 -> RGB, RGB888 -> BGR.
            red = (255, 0, 0) if self.config["main"]["format"] == "BGR888" else (0, 0, 255)
            cv2.circle(frame, (320, 240), 25, red, -1)
            self.on_capture()
            return frame

        def stop(self):
            self.stopped = True

        def close(self):
            self.closed = True

    return Camera


def test_calibration_detects_red_from_picamera_memory_layout(monkeypatch, camera_factory, capsys):
    camera = camera_factory(0)
    monkeypatch.setattr(calibrate_distance, "Picamera2", lambda index: camera)

    calibrate_distance.main([
        "--color", "red",
        "--ball-diameter-cm", "5",
        "--known-distance-cm", "70",
        "--samples", "1",
    ])

    assert camera.config["main"] == {"size": (640, 480), "format": "BGR888"}
    assert "focal_px =" in capsys.readouterr().out
    assert camera.stopped and camera.closed


def test_runtime_detects_red_from_picamera_memory_layout(monkeypatch, camera_factory):
    camera = camera_factory(0)
    monkeypatch.setattr(camera_live_pipeline, "Picamera2", lambda index: camera)
    pipeline = camera_live_pipeline.CameraLivePerceptionPipeline(autostart=False)
    camera.on_capture = pipeline._stop_event.set

    pipeline._capture_loop()
    detection = pipeline.detect(target="red")

    assert camera.config["main"] == {"size": (640, 480), "format": "BGR888"}
    assert detection is not None
    assert detection.label == "red_ball"
    assert detection.diameter_px == pytest.approx(50, rel=0.05)
    assert detection.distance_cm is not None
    assert camera.stopped and camera.closed
