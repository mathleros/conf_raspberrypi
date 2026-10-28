from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from irobot.config.settings import LLMSettings, RuntimeSettings, load_llm_settings
from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.domain.skills import FollowObjectSkill, FollowTargetSkill
from irobot.interfaces import voice_runtime as vr
from irobot.interfaces.intent_parser import Intent, IntentParser
from irobot.interfaces.text_normalizer import fr_numbers_to_digits, preprocess
from irobot.interfaces.voice_runtime import VoiceRuntime
from tests.unit.fake_robot import FakeRobot
from tests.unit.test_follow_object_wiring import World


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


# --------------------------------------------------------------------------- Étape 8 : LLM local (Qwen2.5-1.5B)

USE_CASE = "cherche la balle jaune approche toi à un mètre de la balle jaune puis suis la pendant cinq minutes"
USE_CASE_NORMALIZED = (
    "cherche la balle jaune approche toi à 100 centimètres de la balle jaune puis suis la pendant 300 secondes"
)
USE_CASE_PLAN = {
    "steps": [
        {"intent": "search_and_approach_object", "target": "yellow", "parameters": {"stand_off_cm": 100}},
        {"intent": "follow_object", "target": "yellow", "parameters": {"stand_off_cm": 100, "duration_s": 300}},
    ]
}
MOVES = {"forward", "backward", "left", "right"}


class _FakeResponse:
    def __init__(self, content: str = "", status_code: int = 200):
        self.status_code = status_code
        self._content = content

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


class _FakeLLM:
    """Remplace requests.post : enregistre les appels et rejoue des réponses."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(response, Exception):
            raise response
        if isinstance(response, _FakeResponse):
            return response
        return _FakeResponse(response if isinstance(response, str) else json_dumps(response))

    def user_text(self, index: int = 0) -> str:
        return self.calls[index]["json"]["messages"][-1]["content"]


def json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


@pytest.fixture
def fake_llm(monkeypatch):
    def _install(*responses):
        llm = _FakeLLM(*responses)
        monkeypatch.setattr(vr.requests, "post", llm)
        return llm

    for key in ("LLM_MODEL", "LLM_CONNECT_TIMEOUT_SECONDS", "LLM_READ_TIMEOUT_SECONDS",
                "LLM_MAX_TOKENS_PLAN", "LLM_MAX_TOKENS_INTENT"):
        monkeypatch.delenv(key, raising=False)
    return _install


def _load_eval_script():
    path = Path(__file__).resolve().parents[2] / "scripts" / "test" / "eval_prompt_plan.py"
    spec = importlib.util.spec_from_file_location("eval_prompt_plan", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("tourne de quatre vingt dix degrés", "tourne de 90 degrés"),
        ("avance de soixante et onze centimètres", "avance de 71 centimètres"),
        ("recule de deux cent cinquante centimètres", "recule de 250 centimètres"),
        ("avance d'un mètre", "avance d' 100 centimètres"),
        ("approche toi à un mètre", "approche toi à 100 centimètres"),
        ("suis la pendant cinq minutes", "suis la pendant 300 secondes"),
        ("fais un carré", "fais un carré"),
        ("fais un carré de un mètre", "fais un carré de 100 centimètres"),
        ("tourne à gauche de quarante cinq degrés", "tourne à gauche de 45 degrés"),
    ],
)
def test_preprocess_numbers_and_units(text, expected):
    assert preprocess(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("avance pendant 1 minute 30 secondes", "avance pendant 90 secondes"),
        ("suis la pendant deux minutes et quinze secondes", "suis la pendant 135 secondes"),
        ("suis la pendant une minute trente secondes", "suis la pendant 90 secondes"),
        ("avance de 1 mètre 50", "avance de 150 centimètres"),
        ("avance d'un mètre cinquante", "avance d' 150 centimètres"),
        ("recule de 1 mètre et 20 centimètres", "recule de 120 centimètres"),
        ("avance de deux mètres cinq centimètres", "avance de 205 centimètres"),
        ("avance de 1 mètre 50 puis tourne", "avance de 150 centimètres puis tourne"),
        # formes simples conservées
        ("suis la pendant cinq minutes", "suis la pendant 300 secondes"),
        ("recule de deux mètres", "recule de 200 centimètres"),
        # pas de fusion quand M porte une autre unité ou dépasse 99
        ("avance de 1 mètre et 2 secondes", "avance de 100 centimètres et 2 secondes"),
        ("avance de 1 mètre 150 centimètres", "avance de 100 centimètres 150 centimètres"),
        ("avance 2 mètres 3 fois", "avance 200 centimètres 3 fois"),
    ],
)
def test_preprocess_compound_durations_and_distances(text, expected):
    assert preprocess(text) == expected


def test_local_parser_keeps_own_minute_handling():
    assert IntentParser().parse("avance pendant 1 minute 30 secondes").parameters == {"duration": 90.0}


def test_normalizer_and_prompt_match_eval_script():
    script = _load_eval_script()
    corpus = [case[1] for case in script.CASES] + [
        "quatre vingt dix", "soixante et onze", "deux cent cinquante", "mille deux cent",
        "un carré", "une minute", "dix-sept secondes", "quatre-vingts", "cent un mètres",
    ]
    for text in corpus:
        assert fr_numbers_to_digits(text) == script.fr_numbers_to_digits(text), text
        assert preprocess(text) == script.preprocess(text), text
    assert vr.SYSTEM_PROMPT_PLAN == script.SYSTEM_PROMPT_PLAN


def test_single_intent_prompt_lists_same_intents_as_plan_prompt():
    intents_block = vr.SYSTEM_PROMPT_PLAN.split("Intents :\n", 1)[1].split("\nRègles", 1)[0]
    assert intents_block in vr.SYSTEM_PROMPT
    assert '"confidence"' in vr.SYSTEM_PROMPT
    assert "Exemples" not in vr.SYSTEM_PROMPT


def test_local_parser_understands_spelled_distances_and_angles():
    parser = IntentParser()

    forward = parser.parse("avance de cinquante centimètres")
    turn = parser.parse("tourne à droite de quatre vingt dix degrés")
    backward = parser.parse("recule de deux mètres")
    timed = parser.parse("avance pendant trois secondes")

    assert (forward.name, forward.parameters) == ("move_forward", {"distance": 50.0, "unit": "cm"})
    assert forward.raw_text == "avance de cinquante centimètres"
    assert (turn.name, turn.parameters) == ("turn_right", {"angle": 90.0, "unit": "degrees"})
    assert backward.parameters == {"distance": 2.0, "unit": "m"}
    assert timed.parameters == {"duration": 3.0}
    assert parser.parse("avance").parameters == {"duration": 1.0}


def test_llm_use_case_plan_runs_end_to_end(fake_llm, tmp_path):
    llm = fake_llm(USE_CASE_PLAN)
    world = World(distance_cm=180.0)
    settings = RuntimeSettings()
    registry = SkillRegistry.default()
    registry.register(FollowTargetSkill(settings=settings, time_fn=world.time, sleep_fn=world.sleep))
    registry.register(FollowObjectSkill(settings=settings, time_fn=world.time, sleep_fn=world.sleep))
    runtime = VoiceRuntime(robot=world, perception=world, registry=registry, use_llm=True, trace_dir=str(tmp_path))

    result = runtime.handle_text_as_plan(USE_CASE)

    assert len(llm.calls) == 1
    payload = llm.calls[0]["json"]
    assert llm.user_text() == USE_CASE_NORMALIZED
    assert payload["messages"][0] == {"role": "system", "content": vr.SYSTEM_PROMPT_PLAN}
    assert payload["model"] == "qwen2.5-1.5b"
    assert payload["temperature"] == 0.0
    assert payload["max_tokens"] == 160
    assert payload["stream"] is False
    assert payload["cache_prompt"] is True
    assert payload["response_format"] == {"type": "json_object"}
    assert llm.calls[0]["timeout"] == (1.0, 4.0)

    assert result["status"] == "accepted", result
    assert result["source"] == "llm_plan"
    steps = result["steps"]
    assert [s["intent"].name for s in steps] == ["search_and_approach_object", "follow_object"]
    assert all(s["intent"].raw_text == USE_CASE for s in steps)
    assert steps[1]["intent"].parameters["duration_s"] == 300
    assert steps[1]["intent"].parameters["stand_off_cm"] == 100
    assert set(world.targets) == {"yellow"}
    assert world.now >= 300.0
    assert world.commands[-1] == "stop"

    events = [json.loads(line) for line in Path(result["trace_path"]).read_text(encoding="utf-8").splitlines()]
    plan_raw = next(e for e in events if e["event"] == "plan_raw")
    assert plan_raw["normalized_text"] == USE_CASE_NORMALIZED
    assert plan_raw["intents"][0]["raw_text"] == USE_CASE
    assert next(e for e in events if e["event"] == "input")["text"] == USE_CASE


def test_llm_plan_accepts_backtick_wrapped_json(fake_llm):
    fake_llm("```json\n" + json_dumps({"steps": [{"intent": "stop", "target": None, "parameters": {}}]}) + "\n```")

    intents, trace = vr.ask_llm_for_intent_plan_with_trace("arrête toi")

    assert [i.name for i in intents] == ["stop"]
    assert trace["source"] == "llm_plan"


def test_llm_plan_invalid_json_falls_back_to_parser(fake_llm):
    fake_llm("ceci n'est pas du json")

    intents, trace = vr.ask_llm_for_intent_plan_with_trace("avance de cinquante centimètres")

    assert trace["source"] == "local_parser_fast_fallback"
    assert trace["reason"] == "invalid json"
    assert [(i.name, i.parameters) for i in intents] == [("move_forward", {"distance": 50.0, "unit": "cm"})]
    assert intents[0].raw_text == "avance de cinquante centimètres"


@pytest.mark.parametrize(
    "response",
    [{"plan": []}, {"steps": "avance"}, _FakeResponse(status_code=500)],
)
def test_llm_plan_missing_steps_or_http_error_falls_back(fake_llm, response):
    fake_llm(response)

    intents, trace = vr.ask_llm_for_intent_plan_with_trace("avance")

    assert trace["source"] == "local_parser_fast_fallback"
    assert [i.name for i in intents] == ["move_forward"]


def test_llm_plan_timeout_falls_back_to_parser(fake_llm):
    import requests

    fake_llm(requests.Timeout("read timeout"))

    intents, trace = vr.ask_llm_for_intent_plan_with_trace("recule")

    assert trace["source"] == "local_parser_fast_fallback"
    assert "Timeout" in trace["error"]
    assert [i.name for i in intents] == ["move_backward"]


def test_llm_plan_skips_only_malformed_steps(fake_llm):
    fake_llm(
        {
            "steps": [
                {"intent": "move_forward", "parameters": {"distance": 20}},
                "turn_left",
                {"intent": "turn_left", "parameters": ["angle", 90]},
                {"intent": "turn_right", "parameters": {"angle": 45}, "confidence": 0.95},
            ]
        }
    )

    intents, trace = vr.ask_llm_for_intent_plan_with_trace("avance puis tourne")

    assert [i.name for i in intents] == ["move_forward", "turn_right"]
    assert trace["skipped_steps"] == [1, 2]
    assert intents[0].confidence == 0.8
    assert intents[1].confidence == 0.95


def test_llm_plan_only_malformed_steps_falls_back(fake_llm):
    fake_llm({"steps": ["avance", 3]})

    intents, trace = vr.ask_llm_for_intent_plan_with_trace("avance")

    assert trace["source"] == "local_parser_fast_fallback"
    assert [i.name for i in intents] == ["move_forward"]


def test_llm_step_without_unit_is_treated_as_cm(fake_llm):
    fake_llm({"steps": [{"intent": "move_forward", "target": None, "parameters": {"distance": 50}}]})
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True)

    result = runtime.handle_text_as_plan("avance de cinquante centimètres")

    assert result["status"] == "accepted"
    params = result["steps"][0]["intent"].parameters
    assert params["unit"] == "cm"
    assert params["distance"] == 50.0


def test_llm_http_400_retries_once_without_response_format(fake_llm):
    llm = fake_llm(
        _FakeResponse(status_code=400),
        json_dumps({"steps": [{"intent": "stop", "target": None, "parameters": {}}]}),
    )

    intents, trace = vr.ask_llm_for_intent_plan_with_trace("stop")

    assert len(llm.calls) == 2
    assert "response_format" in llm.calls[0]["json"]
    assert "response_format" not in llm.calls[1]["json"]
    assert llm.calls[1]["json"]["cache_prompt"] is True
    assert trace["source"] == "llm_plan"
    assert [i.name for i in intents] == ["stop"]


def test_llm_http_400_twice_falls_back_after_single_retry(fake_llm):
    llm = fake_llm(_FakeResponse(status_code=400))

    _, trace = vr.ask_llm_for_intent_plan_with_trace("avance")

    assert len(llm.calls) == 2
    assert trace["source"] == "local_parser_fast_fallback"


def test_llm_settings_from_environment(fake_llm, monkeypatch):
    llm = fake_llm({"steps": [{"intent": "stop"}]}, {"intent": "stop"})
    monkeypatch.setenv("LLM_MODEL", "mon-modele")
    monkeypatch.setenv("LLM_CONNECT_TIMEOUT_SECONDS", "0.5")
    monkeypatch.setenv("LLM_READ_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("LLM_MAX_TOKENS_PLAN", "64")
    monkeypatch.setenv("LLM_MAX_TOKENS_INTENT", "32")

    vr.ask_llm_for_intent_plan_with_trace("stop")
    vr.ask_llm_for_intent("stop")

    assert llm.calls[0]["json"]["model"] == "mon-modele"
    assert llm.calls[0]["json"]["max_tokens"] == 64
    assert llm.calls[0]["timeout"] == (0.5, 2.5)
    assert llm.calls[1]["json"]["model"] == "mon-modele"
    assert llm.calls[1]["json"]["max_tokens"] == 32


def test_load_llm_settings_defaults_and_invalid_values():
    assert load_llm_settings({}) == LLMSettings(
        model="qwen2.5-1.5b",
        connect_timeout_seconds=1.0,
        read_timeout_seconds=4.0,
        max_tokens_plan=160,
        max_tokens_intent=96,
    )
    invalid = load_llm_settings(
        {"LLM_MODEL": " ", "LLM_READ_TIMEOUT_SECONDS": "abc", "LLM_MAX_TOKENS_PLAN": "-3",
         "LLM_CONNECT_TIMEOUT_SECONDS": "nan"}
    )
    assert invalid == LLMSettings()


def test_ask_llm_for_intent_uses_preprocessed_text_and_short_output(fake_llm):
    llm = fake_llm({"intent": "move_forward", "target": None, "parameters": {"distance": 50}})

    intent = vr.ask_llm_for_intent("avance de cinquante centimètres")

    payload = llm.calls[0]["json"]
    assert llm.user_text() == "avance de 50 centimètres"
    assert payload["messages"][0]["content"] == vr.SYSTEM_PROMPT
    assert payload["max_tokens"] == 96
    assert payload["temperature"] == 0.0
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["cache_prompt"] is True
    assert intent.name == "move_forward"
    assert intent.confidence == 0.8
    assert intent.raw_text == "avance de cinquante centimètres"


def test_ask_llm_for_intent_malformed_parameters_falls_back(fake_llm):
    fake_llm({"intent": "move_forward", "parameters": "vite"})

    intent = vr.ask_llm_for_intent("avance de cinquante centimètres")

    assert intent.parameters == {"distance": 50.0, "unit": "cm"}


def test_unsupported_command_is_rejected_without_parser_or_motion(fake_llm, monkeypatch, tmp_path):
    fake_llm({"steps": []})

    def _no_parser(*_args, **_kwargs):
        raise AssertionError("le parseur local ne doit pas être utilisé")

    monkeypatch.setattr(IntentParser, "parse_plan", _no_parser)
    robot = FakeRobot()
    runtime = VoiceRuntime(robot=robot, use_llm=True, trace_dir=str(tmp_path))

    result = runtime.handle_text_as_plan("fais un salto arrière")

    assert result["status"] == "rejected"
    assert result["reason"] == "unsupported command"
    assert result["source"] == "llm_unsupported"
    assert result["steps"] == []
    assert not MOVES & set(robot.commands)
    assert robot.commands == []
    events = [json.loads(line) for line in Path(result["trace_path"]).read_text(encoding="utf-8").splitlines()]
    unsupported = [e for e in events if e["event"] == "plan_unsupported"]
    assert len(unsupported) == 1
    assert unsupported[0]["text"] == "fais un salto arrière"
    assert "step_result" not in {e["event"] for e in events}


def test_warm_up_sends_plan_system_prompt_in_background(fake_llm):
    llm = fake_llm({"steps": []})

    thread = vr.warm_up_llm_async()
    thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert thread.daemon
    payload = llm.calls[0]["json"]
    assert payload["messages"][0]["content"] == vr.SYSTEM_PROMPT_PLAN
    assert payload["cache_prompt"] is True
    assert payload["max_tokens"] == 1


def test_warm_up_swallows_errors(fake_llm):
    import requests

    fake_llm(requests.ConnectionError("refused"))

    assert vr.warm_up_llm() is False
