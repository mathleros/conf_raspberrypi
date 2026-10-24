from __future__ import annotations

from irobot.interfaces.voice_runtime import VoiceRuntime
from tests.unit.fake_robot import FakeRobot


def test_voice_runtime_handles_follow_red_ball_command():
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=False)

    result = runtime.handle_text("va vers la balle rouge")

    assert result["status"] == "accepted"
    assert "detect_object" in result["plan"]
    assert "follow_target" in result["plan"]
    assert len(result["results"]) > 0


def test_voice_runtime_handles_stop_command():
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=False)

    result = runtime.handle_text("stop maintenant")

    assert result["status"] == "accepted"
    assert result["plan"] == ["stop_motion"]


def test_voice_runtime_rejects_unknown_command():
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=False)

    result = runtime.handle_text("commande totalement inconnue")

    assert result["status"] == "rejected"
    assert result["reason"] == "intent not allowed"
