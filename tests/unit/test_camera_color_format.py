import importlib
import sys
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from irobot.common.tools import calibrate_distance
from irobot.common.hardware.camera import camera_live_perception_pipeline
from irobot.common.config.settings import RuntimeSettings
from irobot.common.hardware.camera.frame_enhancer import FrameEnhancer
from tests.unit.perception_helpers import camera_target


@pytest.fixture
def camera_factory():
    class Camera:
        camera_controls = {"ExposureValue": (-8.0, 8.0, 0.0)}

        @staticmethod
        def global_camera_info():
            return [{"Model": "ov5647"}]

        def __init__(self, index):
            self.config = None
            self.stopped = False
            self.closed = False
            self.captures = 0
            self.on_capture = lambda: None
            self.controls = {}
            self.red_level = 255
            self.calls = []

        def create_preview_configuration(self, **kwargs):
            return kwargs

        def configure(self, config):
            self.config = config
            self.calls.append("configure")

        def start(self):
            self.calls.append("start")

        def set_controls(self, controls):
            self.controls.update(controls)
            self.calls.append("exposure")

        def capture_array(self):
            self.captures += 1
            if self.captures > 3:
                raise RuntimeError("La calibration ne détecte pas la cible synthétique rouge.")
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            # Ordre mémoire Picamera2 : BGR888 -> RGB, RGB888 -> BGR.
            red = (
                (self.red_level, 0, 0) if self.config["main"]["format"] == "BGR888"
                else (0, 0, self.red_level)
            )
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
    assert camera.controls == {"ExposureValue": 1.0}
    assert "focal_px =" in capsys.readouterr().out
    assert camera.stopped and camera.closed


def test_runtime_detects_red_from_picamera_memory_layout(monkeypatch, camera_factory):
    camera = camera_factory(0)
    monkeypatch.setattr(camera_live_perception_pipeline, "Picamera2", lambda index: camera)
    pipeline = camera_live_perception_pipeline.CameraLivePerceptionPipeline(autostart=False)
    strategy = camera_target(pipeline, "red")
    pipeline.detect(target=strategy)
    camera.on_capture = pipeline._stop_event.set

    pipeline._capture_loop()
    detection = pipeline.detect(target=strategy)

    assert camera.config["main"] == {"size": (640, 480), "format": "BGR888"}
    assert camera.controls == {"ExposureValue": 1.0}
    assert detection is not None
    assert detection.label == "red_ball"
    assert detection.diameter_px == pytest.approx(50, rel=0.05)
    assert detection.distance_cm is not None
    assert camera.stopped and camera.closed


def _entrypoint(monkeypatch, name, camera):
    monkeypatch.setenv("DISPLAY", ":test")
    class Factory:
        global_camera_info = staticmethod(lambda: [{"Model": "ov5647"}])

        def __new__(cls, index):
            return camera

    monkeypatch.setitem(sys.modules, "picamera2", SimpleNamespace(Picamera2=Factory))
    module_name = (
        "irobot.common.tools.vision_diagnostic"
        if name == "vision_diagnostic"
        else f"irobot.common.tools.{name}"
    )
    module = importlib.import_module(module_name)
    if hasattr(module, "Picamera2"):
        monkeypatch.setattr(module, "Picamera2", Factory)
    monkeypatch.setattr(
        module, "load_runtime_settings",
        lambda: RuntimeSettings(camera_clahe_enabled=True, camera_exposure_value=1.0),
    )
    monkeypatch.setattr(cv2, "imshow", lambda *args: None)
    monkeypatch.setattr(cv2, "waitKey", lambda *args: ord("q"))
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
    return module


@pytest.mark.parametrize("name", ["calibrate_distance", "vision_diagnostic"])
def test_camera_tools_apply_shared_rgb_enhancer(monkeypatch, camera_factory, name, capsys):
    camera = camera_factory(0)
    camera.red_level = 78
    module = _entrypoint(monkeypatch, name, camera)
    calls = []
    original_apply = FrameEnhancer.apply

    def apply(enhancer, frame):
        calls.append(frame.copy())
        return original_apply(enhancer, frame)

    monkeypatch.setattr(FrameEnhancer, "apply", apply)
    if name == "calibrate_distance":
        module.main(["--color", "red", "--known-distance-cm", "70", "--samples", "1"])
        assert "focal_px =" in capsys.readouterr().out
    else:
        module.main(["--preview-only"])
        assert "Aperçu caméra uniquement" in capsys.readouterr().out
    assert len(calls) == 1
    assert calls[0].shape == (640, 480, 3)
    assert calls[0][320, 239].tolist() == [78, 0, 0]
    assert camera.calls == ["configure", "exposure", "start"]
    assert camera.stopped and camera.closed


@pytest.mark.parametrize("name", ["calibrate_distance", "vision_diagnostic"])
def test_exposure_failure_releases_camera(monkeypatch, camera_factory, name):
    camera = camera_factory(0)
    module = _entrypoint(monkeypatch, name, camera)

    def fail(controls):
        raise RuntimeError("exposure rejected")

    monkeypatch.setattr(camera, "set_controls", fail)
    with pytest.raises(RuntimeError, match="exposure rejected"):
        if name == "calibrate_distance":
            module.main([])
        else:
            module.main(["--preview-only"])
    assert camera.calls == ["configure"]
    assert camera.captures == 0
    assert camera.closed


def test_exposure_failure_is_logged_and_releases_runtime_camera(monkeypatch, camera_factory, caplog):
    camera = camera_factory(0)
    monkeypatch.setattr(camera_live_perception_pipeline, "Picamera2", lambda index: camera)
    monkeypatch.setattr(
        camera_live_perception_pipeline, "load_runtime_settings",
        lambda: RuntimeSettings(camera_exposure_value=1.0),
    )

    def fail(controls):
        raise RuntimeError("exposure rejected")

    monkeypatch.setattr(camera, "set_controls", fail)
    pipeline = camera_live_perception_pipeline.CameraLivePerceptionPipeline(autostart=False)
    pipeline._capture_loop()
    assert pipeline.detect(target=camera_target(pipeline, "red")) is None
    assert camera.closed
    assert camera.captures == 0
    assert "exposure rejected" in caplog.text
