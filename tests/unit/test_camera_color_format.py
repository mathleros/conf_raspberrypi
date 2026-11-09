import importlib
import sys
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from irobot.tools import calibrate_distance
from irobot.app.hardware.camera import camera_live_perception_pipeline
from irobot.app.config.settings import RuntimeSettings, load_runtime_settings

from irobot.app.hardware.camera.frame_enhancer import FrameEnhancer
from tests.unit.perception_helpers import camera_target

SETTINGS = load_runtime_settings()
CAPTURE_W, CAPTURE_H = SETTINGS.camera_capture_size_px
ORIENTED_W, ORIENTED_H = SETTINGS.camera_oriented_frame_size_px

CAPTURE_SIZE_PX = [CAPTURE_W, CAPTURE_H]
ORIENTED_FRAME_SIZE_PX = [ORIENTED_W, ORIENTED_H]
EXPECTED_MAIN_CONFIG = {"size": (CAPTURE_SIZE_PX[0], CAPTURE_SIZE_PX[1]), "format": "BGR888"}

CAMERA_MODEL = "ov5647"
EXPOSURE_CONTROL_RANGE = (-8.0, 8.0, 0.0)
EXPOSURE_VALUE = 1.0
CLAHE_ENABLED = True
EXPOSURE_ERROR_MESSAGE = "exposure rejected"

MAX_CAPTURES = 3
CAPTURE_ERROR_MESSAGE = "La calibration ne détecte pas la cible synthétique rouge."
RED_LEVEL_DEFAULT = 255
RED_LEVEL_ENHANCER = 78
DISC_CENTER_XY = (CAPTURE_SIZE_PX[0] // 2, CAPTURE_SIZE_PX[1] // 2)
DISC_RADIUS_PX = 25
# Après cv2.ROTATE_90_CLOCKWISE, x devient la ligne et y est inversé en colonne (hauteur brute - 1 - y).
DISC_CENTER_ROTATED_RC = (DISC_CENTER_XY[0], CAPTURE_SIZE_PX[1] - 1 - DISC_CENTER_XY[1])

COLOR = "red"
BALL_DIAMETER_CM = "5"
KNOWN_DISTANCE_CM = "70"
SAMPLES = "1"
EXPECTED_BALL_DIAMETER_PX = 2 * DISC_RADIUS_PX
DIAMETER_REL_TOLERANCE = 0.05
EXPECTED_LABEL = "red_ball"

PREVIEW_ONLY_ARG = "--preview-only"
PREVIEW_MESSAGE = "Aperçu caméra uniquement"
FOCAL_OUTPUT = "focal_px ="
DISPLAY_VALUE = ":test"
QUIT_KEY = ord("q")

@pytest.fixture
def camera_factory():
    class Camera:
        camera_controls = {"ExposureValue": EXPOSURE_CONTROL_RANGE}

        @staticmethod
        def global_camera_info():
            return [{"Model": CAMERA_MODEL}]

        def __init__(self, index):
            self.config = None
            self.stopped = False
            self.closed = False
            self.captures = 0
            self.on_capture = lambda: None
            self.controls = {}
            self.red_level = RED_LEVEL_DEFAULT
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
            if self.captures > MAX_CAPTURES:
                raise RuntimeError(CAPTURE_ERROR_MESSAGE)
            frame = np.zeros((ORIENTED_FRAME_SIZE_PX[0], ORIENTED_FRAME_SIZE_PX[1], 3), dtype=np.uint8)
            # Ordre mémoire Picamera2 : BGR888 -> RGB, RGB888 -> BGR.
            red = (
                (self.red_level, 0, 0) if self.config["main"]["format"] == "BGR888"
                else (0, 0, self.red_level)
            )
            cv2.circle(frame, DISC_CENTER_XY, DISC_RADIUS_PX, red, -1)
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
        "--color", COLOR,
        "--ball-diameter-cm", BALL_DIAMETER_CM,
        "--known-distance-cm", KNOWN_DISTANCE_CM,
        "--samples", SAMPLES,
    ])

    assert camera.config["main"] == EXPECTED_MAIN_CONFIG
    assert camera.controls == {"ExposureValue": EXPOSURE_VALUE}
    assert FOCAL_OUTPUT in capsys.readouterr().out
    assert camera.stopped and camera.closed


def test_runtime_detects_red_from_picamera_memory_layout(monkeypatch, camera_factory):
    camera = camera_factory(0)
    monkeypatch.setattr(camera_live_perception_pipeline, "Picamera2", lambda index: camera)
    pipeline = camera_live_perception_pipeline.CameraLivePerceptionPipeline(autostart=False)
    strategy = camera_target(pipeline, COLOR)
    pipeline.detect(target=strategy)
    camera.on_capture = pipeline._stop_event.set

    pipeline._capture_loop()
    detection = pipeline.detect(target=strategy)

    assert camera.config["main"] == EXPECTED_MAIN_CONFIG
    assert camera.controls == {"ExposureValue": EXPOSURE_VALUE}
    assert detection is not None
    assert detection.label == EXPECTED_LABEL
    assert detection.diameter_px == pytest.approx(EXPECTED_BALL_DIAMETER_PX, rel=DIAMETER_REL_TOLERANCE)
    assert detection.distance_cm is not None
    assert camera.stopped and camera.closed


def _entrypoint(monkeypatch, name, camera):
    monkeypatch.setenv("DISPLAY", DISPLAY_VALUE)
    class Factory:
        global_camera_info = staticmethod(lambda: [{"Model": CAMERA_MODEL}])

        def __new__(cls, index):
            return camera

    monkeypatch.setitem(sys.modules, "picamera2", SimpleNamespace(Picamera2=Factory))
    module_name = (
        "irobot.tools.vision_diagnostic"
        if name == "vision_diagnostic"
        else f"irobot.tools.{name}"
    )
    module = importlib.import_module(module_name)
    if hasattr(module, "Picamera2"):
        monkeypatch.setattr(module, "Picamera2", Factory)
    monkeypatch.setattr(
        module, "load_runtime_settings",
        lambda: RuntimeSettings(camera_clahe_enabled=CLAHE_ENABLED, camera_exposure_value=EXPOSURE_VALUE),
    )
    monkeypatch.setattr(cv2, "imshow", lambda *args: None)
    monkeypatch.setattr(cv2, "waitKey", lambda *args: QUIT_KEY)
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: None)
    return module


@pytest.mark.parametrize("name", ["calibrate_distance", "vision_diagnostic"])
def test_camera_tools_apply_shared_rgb_enhancer(monkeypatch, camera_factory, name, capsys):
    camera = camera_factory(0)
    camera.red_level = RED_LEVEL_ENHANCER
    module = _entrypoint(monkeypatch, name, camera)
    calls = []
    original_apply = FrameEnhancer.apply

    def apply(enhancer, frame):
        calls.append(frame.copy())
        return original_apply(enhancer, frame)

    monkeypatch.setattr(FrameEnhancer, "apply", apply)
    if name == "calibrate_distance":
        module.main(["--color", COLOR, "--known-distance-cm", KNOWN_DISTANCE_CM, "--samples", SAMPLES])
        assert FOCAL_OUTPUT in capsys.readouterr().out
    else:
        module.main([PREVIEW_ONLY_ARG])
        assert PREVIEW_MESSAGE in capsys.readouterr().out
    assert len(calls) == 1
    assert calls[0].shape == (CAPTURE_SIZE_PX[0], CAPTURE_SIZE_PX[1], 3)
    assert calls[0][DISC_CENTER_ROTATED_RC].tolist() == [RED_LEVEL_ENHANCER, 0, 0]
    assert camera.calls == ["configure", "exposure", "start"]
    assert camera.stopped and camera.closed


@pytest.mark.parametrize("name", ["calibrate_distance", "vision_diagnostic"])
def test_exposure_failure_releases_camera(monkeypatch, camera_factory, name):
    camera = camera_factory(0)
    module = _entrypoint(monkeypatch, name, camera)

    def fail(controls):
        raise RuntimeError(EXPOSURE_ERROR_MESSAGE)

    monkeypatch.setattr(camera, "set_controls", fail)
    with pytest.raises(RuntimeError, match=EXPOSURE_ERROR_MESSAGE):
        if name == "calibrate_distance":
            module.main([])
        else:
            module.main([PREVIEW_ONLY_ARG])
    assert camera.calls == ["configure"]
    assert camera.captures == 0
    assert camera.closed


def test_exposure_failure_is_logged_and_releases_runtime_camera(monkeypatch, camera_factory, caplog):
    camera = camera_factory(0)
    monkeypatch.setattr(camera_live_perception_pipeline, "Picamera2", lambda index: camera)
    monkeypatch.setattr(
        camera_live_perception_pipeline, "load_runtime_settings",
        lambda: RuntimeSettings(camera_exposure_value=EXPOSURE_VALUE),
    )

    def fail(controls):
        raise RuntimeError(EXPOSURE_ERROR_MESSAGE)

    monkeypatch.setattr(camera, "set_controls", fail)
    pipeline = camera_live_perception_pipeline.CameraLivePerceptionPipeline(autostart=False)
    pipeline._capture_loop()
    assert pipeline.detect(target=camera_target(pipeline, COLOR)) is None
    assert camera.closed
    assert camera.captures == 0
    assert EXPOSURE_ERROR_MESSAGE in caplog.text
