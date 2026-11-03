import threading

import pytest

from irobot.hardware.camera import camera_live_perception_pipeline as camera_module
from irobot.interfaces.voice_runtime import VoiceRuntime
from tests.unit.fake_robot import FakeRobot


def test_close_waits_for_camera_initialization_and_releases_resources(monkeypatch):
    initializing = threading.Event()
    release = threading.Event()
    calls = []

    class Camera:
        camera_controls = {"ExposureValue": (-8.0, 8.0, 0.0)}

        def __init__(self, index):
            pass

        def create_preview_configuration(self, **kwargs):
            return {}

        def configure(self, config):
            initializing.set()
            if not release.wait(5):
                raise TimeoutError("test camera initialization")

        def start(self):
            calls.append("start")

        def set_controls(self, controls):
            assert controls == {"ExposureValue": 1.0}

        def stop(self):
            calls.append("stop")

        def close(self):
            calls.append("close")

    monkeypatch.setattr(camera_module, "Picamera2", Camera)
    pipeline = camera_module.CameraLivePerceptionPipeline()
    try:
        assert initializing.wait(2)
        assert pipeline._thread.daemon is False
        with pytest.raises(TimeoutError, match="thread caméra"):
            pipeline.close(timeout_s=0)
        assert pipeline._thread.is_alive()
    finally:
        release.set()
        pipeline.close()

    assert not pipeline._thread.is_alive()
    assert calls == ["start", "stop", "close"]
    pipeline.close()
    assert calls == ["start", "stop", "close"]


def test_capture_failure_is_logged_and_camera_is_released(monkeypatch, caplog):
    calls = []

    class Camera:
        def __init__(self, index):
            pass

        def create_preview_configuration(self, **kwargs):
            raise RuntimeError("configuration invalide")

        def stop(self):
            calls.append("stop")

        def close(self):
            calls.append("close")

    monkeypatch.setattr(camera_module, "Picamera2", Camera)
    pipeline = camera_module.CameraLivePerceptionPipeline()
    pipeline.close()

    assert not pipeline._thread.is_alive()
    assert calls == ["stop", "close"]
    assert "configuration invalide" in caplog.text


def test_runtime_reports_camera_shutdown_failure_and_still_stops_robot(tmp_path):
    class Perception:
        def close(self):
            raise RuntimeError("fermeture caméra impossible")

    robot = FakeRobot()
    runtime = VoiceRuntime(robot=robot, perception=Perception(), use_llm=False, trace_dir=str(tmp_path))

    with pytest.raises(RuntimeError, match="fermeture caméra"):
        runtime.close()

    assert robot.commands[-1] == "stop"


def test_runtime_cleans_up_robot_after_camera_shutdown(tmp_path):
    class Robot(FakeRobot):
        def __init__(self):
            super().__init__()
            self.cleanup_calls = 0

        def cleanup(self):
            self.cleanup_calls += 1

    robot = Robot()
    runtime = VoiceRuntime(robot=robot, use_llm=False, trace_dir=str(tmp_path))

    runtime.close()

    assert robot.cleanup_calls == 1
    assert robot.commands[-1] == "stop"
