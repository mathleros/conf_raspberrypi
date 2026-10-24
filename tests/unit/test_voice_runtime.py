from __future__ import annotations

from irobot.interfaces.intent_parser import Intent
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


def test_voice_runtime_plan_expands_return_to_start(monkeypatch):
    from irobot.interfaces import voice_runtime as runtime_module

    monkeypatch.setattr(
        runtime_module,
        "ask_llm_for_intent_plan",
        lambda _text: [
            Intent(name="move_forward", parameters={"distance": 20, "unit": "cm"}, confidence=1.0),
            Intent(name="turn_right", parameters={"angle": 90, "unit": "degrees"}, confidence=1.0),
            Intent(name="return_to_start", confidence=1.0),
        ],
    )

    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True)
    result = runtime.handle_text_as_plan("avance, tourne, puis reviens")

    assert result["status"] == "accepted"
    names = [step["intent"].name for step in result["steps"]]
    assert names == ["move_forward", "turn_right", "turn_left", "move_backward"]


def test_voice_runtime_plan_expands_contour_obstacle(monkeypatch):
    from irobot.interfaces import voice_runtime as runtime_module

    monkeypatch.setattr(
        runtime_module,
        "ask_llm_for_intent_plan",
        lambda _text: [
            Intent(
                name="contour_obstacle",
                parameters={"clearance": 20, "unit": "cm"},
                confidence=1.0,
            )
        ],
    )

    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True)
    result = runtime.handle_text_as_plan("contourne l'objet")

    assert result["status"] == "accepted"
    names = [step["intent"].name for step in result["steps"]]
    assert names == ["turn_right", "move_forward", "turn_left", "move_forward", "turn_right"]
