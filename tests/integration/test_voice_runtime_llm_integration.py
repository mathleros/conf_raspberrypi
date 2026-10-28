from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import requests

from irobot.interfaces.voice_runtime import VoiceRuntime
from tests.unit.fake_robot import FakeRobot

LLM_BASE_URL = "http://127.0.0.1:8080"


def _candidate_llama_binaries() -> list[str]:
    bins = []
    for candidate in (
        shutil.which("llama-server"),
        shutil.which("llm-server"),
        "/usr/local/bin/llama-server",
        "/usr/local/bin/llm-server",
        str(Path.home() / ".local" / "bin" / "llama-server"),
        str(Path.home() / "tools" / "llama.cpp" / "build" / "bin" / "llama-server"),
    ):
        if candidate and os.path.exists(candidate):
            bins.append(candidate)
    return bins


def _candidate_model_paths() -> list[str]:
    paths: list[str] = []
    candidates = [
        Path.home() / "models",
        Path.home() / ".cache" / "llama.cpp",
        Path("/opt"),
    ]
    for base in candidates:
        if not base.exists():
            continue
        for file in base.rglob("*.gguf"):
            paths.append(str(file))
    return paths


def _find_llm_launch_config() -> tuple[str, str] | None:
    binaries = _candidate_llama_binaries()
    if not binaries:
        return None
    models = _candidate_model_paths()
    if not models:
        return None
    return binaries[0], models[0]


def _wait_for_llm_ready(timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = requests.get(f"{LLM_BASE_URL}/v1/models", timeout=2)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False


def _start_llm_if_needed() -> bool:
    if _wait_for_llm_ready(timeout=2):
        return True

    config = _find_llm_launch_config()
    if config is None:
        return False

    binary, model = config
    try:
        process = subprocess.Popen(
            [binary, "-m", model, "--host", "127.0.0.1", "--port", "8080", "--ctx-size", "4096", "--threads", "4", "--parallel", "1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False

    try:
        return _wait_for_llm_ready(timeout=40)
    finally:
        if process.poll() is not None and process.returncode not in (0, None):
            process.wait(timeout=5)


def test_voice_runtime_uses_llm_when_available():
    if not _start_llm_if_needed():
        pytest.skip("Aucun LLM local ou modèle GGUF détecté; test d'intégration ignoré.")

    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True)
    result = runtime.handle_text("va vers la balle rouge")

    assert result["status"] == "accepted"
    assert result["intent"].name in {"follow_red_ball", "unknown"}
    assert len(result["plan"]) > 0
