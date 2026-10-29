from __future__ import annotations

from types import SimpleNamespace

import pytest

from irobot.config.settings import RuntimeSettings
from irobot.domain.orchestrator.planner import SkillPlanner
from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.domain.skills import FollowObjectSkill, FollowTargetSkill
from irobot.interfaces.intent_parser import (
    Intent,
    IntentParser,
    IntentValidator,
    _extract_duration,
    _extract_stand_off_cm,
)
from irobot.interfaces.voice_runtime import VoiceRuntime
from tests.unit.fake_robot import FakeRobot

SENTENCE = "cherche la balle jaune, approche toi à 1m de la balle jaune puis suit la pendant 5 min"


def _plan(text: str) -> list[Intent]:
    return IntentParser().parse_plan(text)


def test_parse_plan_full_sentence():
    plan = _plan(SENTENCE)

    assert [i.name for i in plan] == ["search_and_approach_object", "follow_object"]
    search, follow = plan
    assert search.target == "yellow"
    assert search.parameters["stand_off_cm"] == 100.0
    assert follow.target == "yellow"
    assert follow.parameters["stand_off_cm"] == 100.0
    assert follow.parameters["duration_s"] == 300.0
    assert follow.parameters["target_object"] == "yellow"


def test_parse_plan_variants_words_and_red():
    plan = _plan("cherche la balle rouge, approche-toi à 2 mètres, ensuite suis-la pendant cinq minutes")

    assert [i.name for i in plan] == ["search_and_approach_object", "follow_object"]
    assert plan[0].target == "red"
    assert plan[0].parameters["stand_off_cm"] == 200.0
    assert plan[1].target == "red"
    assert plan[1].parameters["duration_s"] == 300.0
    assert plan[1].parameters["stand_off_cm"] == 200.0


def test_parse_plan_spelled_distance_and_cm():
    plan = _plan("cherche la balle jaune puis approche toi à un mètre de la balle puis suivre la 2 minutes")
    assert plan[0].parameters["stand_off_cm"] == 100.0

    plan = _plan("approche toi à 50 cm de la balle jaune et puis suis la pendant 30 secondes")
    assert plan[0].parameters["stand_off_cm"] == 50.0
    assert plan[1].parameters["duration_s"] == 30.0
    assert plan[1].target == "yellow"


def test_parse_plan_single_segment_matches_parse():
    parser = IntentParser()
    assert [i.name for i in parser.parse_plan("avance")] == [parser.parse("avance").name]
    assert [i.name for i in parser.parse_plan("cherche la balle rouge")] == ["follow_red_ball"]


def test_parse_plan_decimal_comma_is_not_a_separator():
    plan = _plan("approche toi à 1,5 m de la balle jaune")
    assert len(plan) == 1
    assert plan[0].parameters["stand_off_cm"] == 150.0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("pendant 5 min", 300.0),
        ("pendant 5 minutes", 300.0),
        ("pendant cinq minutes", 300.0),
        ("pendant vingt et une minutes", 1260.0),
        ("pendant 1 minute 30 secondes", 90.0),
        ("pendant 2s", 2.0),
        ("pendant 2 secondes", 2.0),
        ("sans durée", None),
    ],
)
def test_extract_duration(text, expected):
    assert _extract_duration(text) == expected


def test_extract_stand_off_cm():
    assert _extract_stand_off_cm("à 1 m") == 100.0
    assert _extract_stand_off_cm("à un mètre") == 100.0
    assert _extract_stand_off_cm("à 50 cm") == 50.0
    assert _extract_stand_off_cm("rien") is None


def test_primitive_durations_unchanged():
    intent = IntentParser().parse("avance pendant 3 secondes")
    assert intent.name == "move_forward"
    assert intent.parameters == {"duration": 3.0}


def test_follow_intent_alone_without_target():
    intent = IntentParser().parse("suis la balle")
    assert intent.name == "follow_object"
    assert intent.target is None


def test_validator_follow_object_targets():
    validator = IntentValidator()
    assert validator.validate(Intent(name="follow_object", target="yellow"))
    assert validator.validate(Intent(name="follow_object", target="red"))
    assert validator.validate(Intent(name="follow_object", target=None))
    assert not validator.validate(Intent(name="follow_object", target="blue"))
    assert not validator.validate(Intent(name="follow_object", target="red_ball"))


def test_planner_maps_follow_object():
    assert SkillPlanner.INTENT_TO_SKILLS["follow_object"] == ["follow_object"]
    assert [s.name for s in SkillPlanner().plan("follow_object")] == ["follow_object"]


def test_normalize_synonyms_and_targets():
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=False)
    names = ["follow", "track", "track_object", "follow_target", "suivre", "suit"]
    out = runtime._normalize_plan_intent_names([Intent(name=n, target="balle jaune") for n in names])
    assert all(i.name == "follow_object" and i.target == "yellow" for i in out)
    assert all(i.parameters["target_object"] == "yellow" for i in out)

    out = runtime._normalize_plan_intent_names(
        [
            Intent(name="search_object", target="Rouge"),
            Intent(name="follow_object", target="red_ball"),
            Intent(name="follow_red_ball", target="red_ball"),
            Intent(name="follow_object", parameters={"target_object": "jaune"}),
        ]
    )
    assert [(i.name, i.target) for i in out] == [
        ("search_and_approach_object", "red"),
        ("follow_object", "red"),
        ("follow_red_ball", "red_ball"),
        ("follow_object", "yellow"),
    ]


def test_validate_rejects_follow_object_with_unknown_target():
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=False)
    plan = runtime._normalize_plan_intent_names([Intent(name="follow", target="blue")])
    validated, errors = runtime._validate_intent_plan(plan)
    assert validated == []
    assert errors[0]["reason"] == "intent not allowed"


@pytest.mark.parametrize("name", ["follow_object", "search_and_approach_object"])
def test_sanitize_bounds_parameters(name):
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=False)
    settings = runtime.settings

    high, _ = runtime._validate_intent_plan(
        [Intent(name=name, target="red", parameters={"stand_off_cm": 9999, "duration_s": 99999, "search_timeout_s": 999})]
    )
    assert high[0].parameters["stand_off_cm"] == settings.max_stand_off_cm
    assert high[0].parameters["duration_s"] == settings.max_follow_duration_sec
    assert high[0].parameters["search_timeout_s"] == 120.0

    low, _ = runtime._validate_intent_plan(
        [Intent(name=name, target="red", parameters={"stand_off_cm": 1, "duration_s": -5, "search_timeout_s": 0})]
    )
    assert low[0].parameters["stand_off_cm"] == settings.min_stand_off_cm
    assert low[0].parameters["duration_s"] == 1.0
    assert low[0].parameters["search_timeout_s"] == 1.0

    ok, _ = runtime._validate_intent_plan(
        [Intent(name=name, target="red", parameters={"stand_off_cm": "100", "duration_s": 300})]
    )
    assert ok[0].parameters["stand_off_cm"] == 100.0
    assert ok[0].parameters["duration_s"] == 300.0


def test_sanitize_non_numeric_falls_back_to_defaults():
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=False)
    bad = {"stand_off_cm": "près", "duration_s": None, "search_timeout_s": float("nan")}
    out, _ = runtime._validate_intent_plan([Intent(name="follow_object", target="yellow", parameters=bad)])

    assert out[0].parameters["stand_off_cm"] == 100.0
    assert out[0].parameters["duration_s"] == 60.0
    assert out[0].parameters["search_timeout_s"] == runtime.settings.search_timeout_seconds


def test_sanitize_leaves_absent_keys_absent():
    runtime = VoiceRuntime(robot=FakeRobot(), use_llm=False)
    out, _ = runtime._validate_intent_plan([Intent(name="follow_object", target="yellow")])
    assert out[0].parameters == {}


class World(FakeRobot):
    """Robot + perception simulés avec horloge virtuelle."""

    def __init__(self, distance_cm: float):
        super().__init__()
        self.now = 0.0
        self.distance_cm = distance_cm
        self.targets: list[str | None] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds

    def forward_for(self, duration: float) -> None:
        self.commands.append("forward")
        self.distance_cm -= 25.0 * duration
        self.sleep(duration)

    def backward_for(self, duration: float) -> None:
        self.commands.append("backward")
        self.distance_cm += 25.0 * duration
        self.sleep(duration)

    def left_for(self, duration: float) -> None:
        self.commands.append("left")
        self.sleep(duration)

    def right_for(self, duration: float) -> None:
        self.commands.append("right")
        self.sleep(duration)

    def detect(self, *, target=None):
        self.targets.append(target)
        return SimpleNamespace(label=target, position="center", distance_cm=self.distance_cm)


def test_full_plan_runs_through_voice_runtime(tmp_path):
    world = World(distance_cm=180.0)
    settings = RuntimeSettings()
    registry = SkillRegistry.default()
    registry.register(FollowTargetSkill(settings=settings, time_fn=world.time, sleep_fn=world.sleep))
    registry.register(FollowObjectSkill(settings=settings, time_fn=world.time, sleep_fn=world.sleep))
    runtime = VoiceRuntime(robot=world, perception=world, registry=registry, use_llm=False, trace_dir=str(tmp_path))

    result = runtime.handle_text_as_plan(SENTENCE)

    assert result["status"] == "accepted", result
    steps = result["steps"]
    assert [s["intent"].name for s in steps] == ["search_and_approach_object", "follow_object"]
    assert "follow_target" in steps[0]["plan"]
    assert steps[1]["plan"] == ["follow_object"]
    assert steps[1]["intent"].parameters["duration_s"] == 300.0
    assert set(world.targets) == {"yellow"}
    # Le suivi consomme bien les 5 minutes sur l'horloge virtuelle, sans attente réelle.
    assert world.now >= 300.0
    assert "forward" in world.commands
    assert world.commands[-1] == "stop"
