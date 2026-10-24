from __future__ import annotations

from pathlib import Path

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
        "ask_llm_for_intent_plan_with_trace",
        lambda _text: (
            [
                Intent(name="move_forward", parameters={"distance": 20, "unit": "cm"}, confidence=1.0),
                Intent(name="turn_right", parameters={"angle": 90, "unit": "degrees"}, confidence=1.0),
                Intent(name="return_to_start", confidence=1.0),
            ],
            {"source": "llm_plan"},
        ),
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
        "ask_llm_for_intent_plan_with_trace",
        lambda _text: (
            [
                Intent(
                    name="contour_obstacle",
                    parameters={"clearance": 20, "unit": "cm"},
                    confidence=1.0,
                )
            ],
            {"source": "llm_plan"},
        ),
    )

    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True)
    result = runtime.handle_text_as_plan("contourne l'objet")

    assert result["status"] == "accepted"
    names = [step["intent"].name for step in result["steps"]]
    assert names == ["turn_right", "move_forward", "turn_left", "move_forward", "turn_right"]


def test_voice_runtime_plan_expands_execute_path(monkeypatch):
    from irobot.interfaces import voice_runtime as runtime_module

    monkeypatch.setattr(
        runtime_module,
        "ask_llm_for_intent_plan_with_trace",
        lambda _text: (
            [
                Intent(
                    name="execute_path",
                    parameters={
                        "steps": [
                            {"action": "move_forward", "distance": 40, "unit": "cm"},
                            {"action": "turn_right", "angle": 90},
                            {"action": "move_forward", "distance": 20, "unit": "cm"},
                        ]
                    },
                    confidence=1.0,
                )
            ],
            {"source": "llm_plan"},
        ),
    )

    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True)
    result = runtime.handle_text_as_plan("fais un rectangle")

    assert result["status"] == "accepted"
    names = [step["intent"].name for step in result["steps"]]
    assert names == ["move_forward", "turn_right", "move_forward"]


def test_voice_runtime_plan_rejects_invalid_execute_path_action(monkeypatch):
    from irobot.interfaces import voice_runtime as runtime_module

    monkeypatch.setattr(
        runtime_module,
        "ask_llm_for_intent_plan_with_trace",
        lambda _text: (
            [
                Intent(
                    name="execute_path",
                    parameters={
                        "steps": [
                            {"action": "draw_heart", "distance": 30, "unit": "cm"},
                        ]
                    },
                    confidence=1.0,
                )
            ],
            {"source": "llm_plan"},
        ),
    )

    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True)
    result = runtime.handle_text_as_plan("dessine un coeur")

    assert result["status"] == "rejected"
    assert result["reason"] == "no valid plan step"
    assert len(result["validation_errors"]) >= 1


def test_voice_runtime_plan_normalizes_search_object_synonym(monkeypatch):
    from irobot.interfaces import voice_runtime as runtime_module

    monkeypatch.setattr(
        runtime_module,
        "ask_llm_for_intent_plan_with_trace",
        lambda _text: (
            [
                Intent(
                    name="search_object",
                    parameters={"search": True, "approach": True, "target_object": "bouteille"},
                    confidence=1.0,
                )
            ],
            {"source": "llm_plan"},
        ),
    )

    def _mock_detect(_self, context):
        from irobot.domain.skills.base_skill import SkillResult

        context.state["last_object_position"] = "centre"
        return SkillResult(
            status="success",
            message="mock detect",
            data={"position": "centre"},
            confidence=1.0,
            next_action="align_to_target",
        )

    from irobot.domain.skills.perception.detect_object import DetectObjectSkill

    monkeypatch.setattr(DetectObjectSkill, "execute", _mock_detect)

    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True)
    result = runtime.handle_text_as_plan("cherche un objet puis approche toi")

    assert result["status"] == "accepted"
    assert result["steps"][0]["intent"].name == "search_and_approach_object"
    assert "follow_target" in result["steps"][0]["plan"]


def test_voice_runtime_uses_parser_fallback_when_llm_plan_invalid(monkeypatch):
    from irobot.interfaces import voice_runtime as runtime_module

    monkeypatch.setattr(
        runtime_module,
        "ask_llm_for_intent_plan_with_trace",
        lambda _text: ([Intent(name="unknown", raw_text="bad")], {"source": "llm_error_fallback_single_intent"}),
    )

    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True)
    result = runtime.handle_text_as_plan("avance")

    assert result["source"] == "llm_error_fallback_single_intent"


def test_voice_runtime_writes_trace_log(tmp_path, monkeypatch):
    from irobot.interfaces import voice_runtime as runtime_module

    monkeypatch.setattr(
        runtime_module,
        "ask_llm_for_intent_plan_with_trace",
        lambda _text: ([Intent(name="move_forward", parameters={"distance": 10, "unit": "cm"}, confidence=1.0)], {"source": "llm_plan"}),
    )

    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True, trace_dir=str(tmp_path))
    result = runtime.handle_text_as_plan("avance")

    trace_path = Path(result["trace_path"])
    assert trace_path.exists()
    assert trace_path.read_text(encoding="utf-8").strip() != ""


def test_voice_runtime_mission_timeout(monkeypatch):
    from irobot.interfaces import voice_runtime as runtime_module

    monkeypatch.setattr(
        runtime_module,
        "ask_llm_for_intent_plan_with_trace",
        lambda _text: (
            [Intent(name="move_forward", parameters={"distance": 10, "unit": "cm"}, confidence=1.0)],
            {"source": "llm_plan"},
        ),
    )

    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True)
    runtime.settings = runtime.settings.__class__(
        cm_per_second=runtime.settings.cm_per_second,
        deg_per_second=runtime.settings.deg_per_second,
        step_timeout_seconds=runtime.settings.step_timeout_seconds,
        mission_timeout_seconds=0.0,
        max_step_retries=runtime.settings.max_step_retries,
        max_plan_steps=runtime.settings.max_plan_steps,
        max_distance_cm=runtime.settings.max_distance_cm,
        max_angle_deg=runtime.settings.max_angle_deg,
        max_duration_sec=runtime.settings.max_duration_sec,
    )

    result = runtime.handle_text_as_plan("avance")
    assert result["status"] == "aborted"
