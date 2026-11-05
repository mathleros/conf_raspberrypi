"""Structural limits and offline adapter contracts for the voice runtime."""

import ast
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from irobot.config.settings import RuntimeSettings
from irobot.domain.intent import Intent
from irobot.hardware.audio import voice_input
from irobot.hardware import runtime_factory
from irobot.interfaces import voice_runtime
from irobot.interfaces.intent.llm_intent_parser import ask_llm_for_intent_plan_with_trace


PACKAGE = Path(__file__).resolve().parents[2] / "src" / "irobot"
VOICE_FILES = sorted((PACKAGE / "interfaces").glob("voice*.py")) + [
    PACKAGE / "interfaces" / "command_service.py",
    PACKAGE / "interfaces" / "intent" / "plan_validator.py",
    PACKAGE / "domain" / "orchestrator" / "mission_orchestrator.py",
    PACKAGE / "hardware" / "audio" / "voice_input.py",
    PACKAGE / "hardware" / "runtime_factory.py",
]


@pytest.mark.parametrize("path", VOICE_FILES, ids=lambda path: path.name)
def test_voice_modules_respect_line_limits(path):
    source = path.read_text(encoding="utf-8")
    assert len(source.splitlines()) <= 500, path.name
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = min([node.lineno] + [item.lineno for item in node.decorator_list])
            assert node.end_lineno - start + 1 <= 50, f"{path.name}:{node.name}"


@pytest.mark.parametrize(
    "path", [path for path in VOICE_FILES if path.parent.name == "interfaces"],
    ids=lambda path: path.name,
)
def test_voice_logic_does_not_import_hardware_at_module_load(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Import):
            assert all(not name.name.startswith("irobot.hardware") for name in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("irobot.hardware")


def test_audio_stream_terminates_and_closes_on_consumer_error(monkeypatch):
    stream = BytesIO(b"audio")
    calls = []
    process = SimpleNamespace(
        stdout=stream, poll=lambda: None,
        terminate=lambda: calls.append("terminate"),
        wait=lambda **_: calls.append("wait"),
    )
    monkeypatch.setattr(voice_input.subprocess, "Popen", lambda *_args, **_kwargs: process)
    with pytest.raises(ValueError, match="consumer"):
        with voice_input._arecord_stream("default") as captured:
            assert captured.read() == b"audio"
            raise ValueError("consumer")
    assert calls == ["terminate", "wait"]
    assert stream.closed


def test_audio_stream_kills_when_termination_times_out(monkeypatch):
    stream = BytesIO()
    calls = []

    def wait(**_):
        calls.append("wait")
        if calls.count("wait") == 1:
            raise subprocess.TimeoutExpired("arecord", 1)

    process = SimpleNamespace(
        stdout=stream, poll=lambda: None, terminate=lambda: calls.append("terminate"),
        kill=lambda: calls.append("kill"), wait=wait,
    )
    monkeypatch.setattr(voice_input.subprocess, "Popen", lambda *_args, **_kwargs: process)
    with voice_input._arecord_stream("default"):
        pass
    assert calls == ["terminate", "wait", "kill", "wait"]
    assert stream.closed


def test_audio_stream_rejects_missing_stdout_and_cleans_up(monkeypatch):
    calls = []
    process = SimpleNamespace(
        stdout=None, poll=lambda: None, terminate=lambda: calls.append("terminate"),
        wait=lambda **_: calls.append("wait"),
    )
    monkeypatch.setattr(voice_input.subprocess, "Popen", lambda *_args, **_kwargs: process)
    with pytest.raises(RuntimeError, match="flux audio"):
        with voice_input._arecord_stream("default"):
            pytest.fail("An absent stream must not be yielded")
    assert calls == ["terminate", "wait"]


def test_transcription_uses_fake_vosk_and_skips_empty_results(monkeypatch):
    chunks = iter([b"empty", b"speech", b""])
    calls = []
    results = iter(['{"text":""}', '{"text":" avance " }'])
    recognizer = SimpleNamespace(
        AcceptWaveform=lambda raw: True, Result=lambda: next(results),
        Reset=lambda: calls.append("reset"),
    )

    @contextmanager
    def stream(device):
        calls.append(device)
        yield SimpleNamespace(read=lambda size: next(chunks))
        calls.append("closed")

    def model(path):
        assert path == voice_input.MODEL_PATH
        return "synthetic-model"

    def create_recognizer(loaded, rate):
        assert loaded == "synthetic-model"
        assert rate == 16000
        return recognizer

    monkeypatch.setitem(sys.modules, "vosk", SimpleNamespace(
        Model=model, KaldiRecognizer=create_recognizer,
    ))
    monkeypatch.setattr(voice_input, "_arecord_stream", stream)
    assert list(voice_input.transcribe_loop("synthetic-device")) == ["avance"]
    assert calls == ["synthetic-device", "reset", "closed"]


def test_transcription_reports_missing_vosk(monkeypatch):
    monkeypatch.setitem(sys.modules, "vosk", None)
    with pytest.raises(RuntimeError, match="vosk.*absente"):
        next(voice_input.transcribe_loop("unused"))


def test_hardware_factory_stays_offline_on_mac(monkeypatch):
    monkeypatch.setattr(runtime_factory.sys, "platform", "darwin")
    assert runtime_factory.build_hardware_runtime(settings=RuntimeSettings()) == {
        "robot": None, "camera": None, "sensor": None,
    }


def test_hardware_factory_injects_sensor_and_cleans_resources_separately(monkeypatch):
    from irobot.hardware.smart_car import smart_car
    from irobot.hardware.runtime_factory import close_hardware_runtime

    class Sensor:
        def __init__(self):
            self.cleanup_calls = 0

        def read_distance_cm(self):
            return 25.0

        def cleanup(self):
            self.cleanup_calls += 1

    class Car:
        def __init__(self, *, drive_speed):
            self.speed = drive_speed

        def cleanup(self):
            pass

        def stop(self):
            pass

    sensor = Sensor()
    monkeypatch.setattr(runtime_factory.sys, "platform", "linux")
    monkeypatch.setattr(smart_car, "SmartCar2WD", Car)
    monkeypatch.setitem(
        sys.modules,
        "irobot.hardware.sensors.hc_sr04",
        SimpleNamespace(HC_SR04=lambda: sensor),
    )
    camera_kwargs = {}

    def create_camera(**kwargs):
        camera_kwargs.update(kwargs)
        return object()

    monkeypatch.setitem(
        sys.modules,
        "irobot.hardware.camera.camera_live_perception_pipeline",
        SimpleNamespace(CameraLivePerceptionPipeline=create_camera),
    )

    hardware = runtime_factory.build_hardware_runtime(
        settings=RuntimeSettings(obstacle_threshold_cm=30.0),
    )

    assert hardware["sensor"] is sensor
    assert hardware["sensor"].read_distance_cm() == 25.0
    assert not hasattr(hardware["robot"], "read_distance_cm")
    assert hardware["robot"].check_obstacle() is True
    assert camera_kwargs["sensor"] is sensor
    close_hardware_runtime(hardware)
    assert sensor.cleanup_calls == 1


def test_hardware_factory_cleans_up_if_camera_build_fails(monkeypatch):
    from irobot.hardware.smart_car import smart_car

    calls = []

    class Sensor:
        def read_distance_cm(self):
            return None

        def cleanup(self):
            calls.append("sensor cleanup")

    class Car:
        def __init__(self, *, drive_speed):
            self.speed = drive_speed

        def stop(self):
            calls.append("robot stop")

        def cleanup(self):
            calls.append("robot cleanup")

    def fail_camera(**kwargs):
        raise RuntimeError("camera init failed")

    monkeypatch.setattr(runtime_factory.sys, "platform", "linux")
    monkeypatch.setattr(smart_car, "SmartCar2WD", Car)
    monkeypatch.setitem(
        sys.modules,
        "irobot.hardware.sensors.hc_sr04",
        SimpleNamespace(HC_SR04=Sensor),
    )
    monkeypatch.setitem(
        sys.modules,
        "irobot.hardware.camera.camera_live_perception_pipeline",
        SimpleNamespace(CameraLivePerceptionPipeline=fail_camera),
    )

    with pytest.raises(RuntimeError, match="camera init failed"):
        runtime_factory.build_hardware_runtime(settings=RuntimeSettings())

    assert calls == ["robot stop", "robot cleanup", "sensor cleanup"]


def test_hardware_runtime_cleanup_attempts_every_resource():
    calls = []

    class Robot:
        def stop(self):
            calls.append("stop")
            raise RuntimeError("stop failed")

        def cleanup(self):
            calls.append("robot cleanup")
            raise RuntimeError("robot cleanup failed")

    class Camera:
        def close(self):
            calls.append("camera close")
            raise RuntimeError("camera close failed")

    with pytest.raises(ExceptionGroup) as error:
        runtime_factory.close_hardware_runtime({"robot": Robot(), "camera": Camera()})

    assert len(error.value.exceptions) == 3
    assert calls == ["stop", "robot cleanup", "camera close"]


def test_llm_interpretation_accepts_an_injected_transport():
    def post(payload, timeout, formats, meta=None):
        meta["llm_attempts"] = 1
        return '{"steps":[{"intent":"move_forward","parameters":{"distance":20}}]}'

    intents, trace = ask_llm_for_intent_plan_with_trace("avance de 20 cm", post=post)
    assert [intent.name for intent in intents] == ["move_forward"]
    assert trace["source"] == "llm_plan"
    assert trace["llm_attempts"] == 1


@pytest.mark.parametrize("name", ["spin_360", "move_square", "contour_obstacle"])
def test_expanded_steps_preserve_metadata_and_own_parameters(tmp_path, name):
    runtime = voice_runtime.VoiceRuntime(use_llm=False, trace_dir=str(tmp_path))
    original = Intent(name=name, target="red", confidence=0.7, raw_text="original")
    steps = runtime.command_service.planner.expand_intents([original])
    assert len({id(step.parameters) for step in steps}) == len(steps)
    assert all(step.target == "red" and step.confidence == 0.7 for step in steps)
    assert all(step.raw_text == "original" for step in steps)
    assert original.parameters == {}
