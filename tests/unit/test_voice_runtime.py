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
    assert result["reason"] == "invalid plan step"
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
        lambda _text: ([Intent(name="unknown", raw_text="bad")], {"source": "local_parser_fast_fallback"}),
    )

    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True)
    result = runtime.handle_text_as_plan("avance")

    assert result["source"] == "local_parser_fast_fallback"


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
        step_timeout_seconds=0.0,
        mission_timeout_seconds=0.0,
        max_step_retries=runtime.settings.max_step_retries,
        max_plan_steps=runtime.settings.max_plan_steps,
        max_distance_cm=runtime.settings.max_distance_cm,
        max_angle_deg=runtime.settings.max_angle_deg,
        max_duration_sec=runtime.settings.max_duration_sec,
    )

    result = runtime.handle_text_as_plan("avance")
    assert result["status"] == "aborted"


def _patch_plan(monkeypatch, intents):
    from irobot.interfaces import voice_runtime as runtime_module

    monkeypatch.setattr(
        runtime_module,
        "ask_llm_for_intent_plan_with_trace",
        lambda _text: (intents, {"source": "llm_plan"}),
    )


def test_sanitize_injects_default_duration_and_angle():
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=False)

    forward = runtime._sanitize_primitive_intent(Intent(name="move_forward"))
    backward = runtime._sanitize_primitive_intent(Intent(name="move_backward"))
    turn = runtime._sanitize_primitive_intent(Intent(name="turn_left"))
    turn_timed = runtime._sanitize_primitive_intent(Intent(name="turn_right", parameters={"duration": 2}))

    assert forward.parameters["duration"] == 1.0
    assert backward.parameters["duration"] == 1.0
    assert turn.parameters["angle"] == 90.0
    assert "angle" not in turn_timed.parameters
    assert turn_timed.parameters["duration"] == 2.0


def test_sanitize_default_duration_bounded_by_max_duration():
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=False)
    runtime.settings = runtime.settings.__class__(
        **{**runtime.settings.__dict__, "max_duration_sec": 0.5}
    )

    forward = runtime._sanitize_primitive_intent(Intent(name="move_forward"))

    assert forward.parameters["duration"] == 0.5


def test_sanitize_normalizes_units():
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=False)

    meters = runtime._sanitize_primitive_intent(
        Intent(name="move_forward", parameters={"distance": 1, "unit": "mètres"})
    )
    unknown = runtime._sanitize_primitive_intent(
        Intent(name="move_forward", parameters={"distance": 10, "unit": "furlongs"})
    )

    assert meters.parameters["unit"] == "m"
    assert meters.parameters["distance"] == 1
    assert unknown.parameters["unit"] == "cm"


def test_primitive_resolves_unit_synonyms():
    from irobot.domain.skills.base_skill import SkillContext
    from irobot.domain.skills.primitives.base_motion_primitive import normalize_distance_unit
    from irobot.domain.skills.primitives.move_forward import MoveForwardSkill

    assert normalize_distance_unit("Metres") == "m"
    assert normalize_distance_unit("centimètres") == "cm"
    assert normalize_distance_unit("parsec") == "cm"

    context = SkillContext(
        robot=FakeRobot(), state={"active_intent_parameters": {"distance": 1, "unit": "meters"}}
    )
    payload = MoveForwardSkill()._resolve_motion_parameters(context)
    assert payload["unit"] == "m"


def test_voice_runtime_stops_robot_at_end_of_mission(monkeypatch):
    _patch_plan(monkeypatch, [Intent(name="move_forward", parameters={"distance": 10, "unit": "cm"}, confidence=1.0)])
    robot = FakeRobot()
    runtime = VoiceRuntime(robot=robot, use_llm=True)

    result = runtime.handle_text_as_plan("avance")

    assert result["status"] == "accepted"
    assert robot.commands[-1] == "stop"


def test_voice_runtime_stops_robot_even_after_exception(monkeypatch):
    _patch_plan(monkeypatch, [Intent(name="move_forward", parameters={"distance": 10, "unit": "cm"}, confidence=1.0)])
    robot = FakeRobot()
    runtime = VoiceRuntime(robot=robot, use_llm=True)

    def _boom(_intent):
        raise RuntimeError("boom")

    monkeypatch.setattr(runtime.controller, "handle_intent", _boom)

    try:
        runtime.handle_text_as_plan("avance")
        raised = False
    except RuntimeError:
        raised = True

    assert raised
    assert robot.commands == ["stop"]


def test_voice_runtime_ignores_exception_raised_by_final_stop(monkeypatch):
    _patch_plan(monkeypatch, [Intent(name="move_forward", parameters={"distance": 10, "unit": "cm"}, confidence=1.0)])
    robot = FakeRobot()

    def _bad_stop():
        raise OSError("gpio")

    robot.stop = _bad_stop
    runtime = VoiceRuntime(robot=robot, use_llm=True)

    result = runtime.handle_text_as_plan("avance")

    assert result["status"] == "accepted"


def test_voice_runtime_stops_executing_steps_after_failure(monkeypatch):
    _patch_plan(
        monkeypatch,
        [
            Intent(name="move_forward", parameters={"distance": 10, "unit": "cm"}, confidence=1.0),
            Intent(name="turn_left", parameters={"angle": 90}, confidence=1.0),
        ],
    )
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True)
    seen: list[str] = []

    def _fail(intent):
        seen.append(intent.name)
        return {"intent": intent, "status": "failed", "reason": "nope"}

    monkeypatch.setattr(runtime.controller, "handle_intent", _fail)

    result = runtime.handle_text_as_plan("avance puis tourne")

    assert result["status"] == "incomplete"
    assert len(result["steps"]) == 1
    assert set(seen) == {"move_forward"}


def test_voice_runtime_rejects_whole_plan_when_one_step_invalid(monkeypatch):
    _patch_plan(
        monkeypatch,
        [
            Intent(name="move_forward", parameters={"distance": 10, "unit": "cm"}, confidence=1.0),
            Intent(name="draw_heart", confidence=1.0),
        ],
    )
    robot = FakeRobot()
    runtime = VoiceRuntime(robot=robot, use_llm=True)

    result = runtime.handle_text_as_plan("avance puis dessine")

    assert result["status"] == "rejected"
    assert result["reason"] == "invalid plan step"
    assert len(result["validation_errors"]) == 1
    assert "forward" not in robot.commands


def test_effective_step_timeout_with_and_without_duration():
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=False)
    base = runtime.settings.step_timeout_seconds
    extra = runtime.settings.search_timeout_seconds + runtime.settings.timeout_margin_seconds

    assert runtime._effective_step_timeout(Intent(name="stop")) == base
    assert runtime._effective_step_timeout(Intent(name="follow_target", parameters={"duration_s": 300})) == 300 + extra
    assert runtime._effective_step_timeout(Intent(name="follow_target", parameters={"duration_s": 0})) == max(base, extra)


def test_effective_mission_timeout_is_sum_of_steps():
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=False)
    extra = runtime.settings.search_timeout_seconds + runtime.settings.timeout_margin_seconds
    intents = [
        Intent(name="follow_target", parameters={"duration_s": 300}),
        Intent(name="stop"),
    ]

    expected = max(
        runtime.settings.mission_timeout_seconds,
        300 + extra + runtime.settings.step_timeout_seconds,
    )
    assert runtime._effective_mission_timeout(intents) == expected
    assert runtime._effective_mission_timeout([Intent(name="stop")]) == runtime.settings.mission_timeout_seconds


def test_no_retry_on_aborted_or_timeout(tmp_path):
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=False, trace_dir=str(tmp_path))
    calls = []

    def aborted(_intent):
        calls.append(1)
        return {"status": "aborted", "reason": "x", "results": []}

    runtime.controller.handle_intent = aborted
    result = runtime._execute_intent_with_retry(Intent(name="stop"), tmp_path / "t.jsonl")

    assert result["status"] == "aborted"
    assert len(calls) == 1

    calls.clear()
    runtime.settings = type(runtime.settings)(step_timeout_seconds=-1.0)

    def failed(_intent):
        calls.append(1)
        return {"status": "accepted", "results": []}

    runtime.controller.handle_intent = failed
    result = runtime._execute_intent_with_retry(Intent(name="stop"), tmp_path / "t.jsonl")
    assert result["reason"] == "step timeout"
    assert len(calls) == 1
