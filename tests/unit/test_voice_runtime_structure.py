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
from irobot.hardware.audio import voice_input
from irobot.hardware import voice_runtime_factory
from irobot.interfaces import voice_llm, voice_runtime
from irobot.interfaces.intent_parser import Intent


PACKAGE = Path(__file__).resolve().parents[2] / "src" / "irobot"
VOICE_FILES = sorted((PACKAGE / "interfaces").glob("voice*.py")) + [
    PACKAGE / "hardware" / "audio" / "voice_input.py",
    PACKAGE / "hardware" / "voice_runtime_factory.py",
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
    monkeypatch.setattr(voice_runtime_factory.sys, "platform", "darwin")
    assert voice_runtime_factory.build_hardware_runtime(settings=RuntimeSettings()) == {
        "robot": None, "camera": None, "sensor": None, "perception": None,
    }


def test_hardware_factory_refuses_unqualified_protection(monkeypatch):
    monkeypatch.setattr(voice_runtime_factory.sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="no qualified real P5 adapter"):
        voice_runtime_factory.build_hardware_runtime(
            settings=RuntimeSettings(protection_presence="present"),
        )


def test_llm_interpretation_accepts_an_injected_transport():
    def post(payload, timeout, formats, meta=None):
        meta["llm_attempts"] = 1
        return '{"steps":[{"intent":"move_forward","parameters":{"distance":20}}]}'

    intents, trace = voice_llm.ask_llm_for_intent_plan_with_trace("avance de 20 cm", post=post)
    assert [intent.name for intent in intents] == ["move_forward"]
    assert trace["source"] == "llm_plan"
    assert trace["llm_attempts"] == 1


def test_plan_compatibility_wrapper_uses_the_public_transport(monkeypatch):
    monkeypatch.setattr(
        voice_runtime, "_post_llm_chat",
        lambda *_: '{"steps":[{"intent":"stop","parameters":{}}]}',
    )
    assert [intent.name for intent in voice_runtime.ask_llm_for_intent_plan("stop")] == ["stop"]


@pytest.mark.parametrize("name", ["spin_360", "move_square", "contour_obstacle"])
def test_expanded_steps_preserve_metadata_and_own_parameters(tmp_path, name):
    runtime = voice_runtime.VoiceRuntime(use_llm=False, trace_dir=str(tmp_path))
    original = Intent(name=name, target="red", confidence=0.7, raw_text="original")
    steps = runtime._expand_high_level_intents([original])
    assert len({id(step.parameters) for step in steps}) == len(steps)
    assert all(step.target == "red" and step.confidence == 0.7 for step in steps)
    assert all(step.raw_text == "original" for step in steps)
    assert original.parameters == {}
