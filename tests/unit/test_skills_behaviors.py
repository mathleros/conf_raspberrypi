from __future__ import annotations

from types import SimpleNamespace

import pytest

from irobot.common.config.settings import RuntimeSettings
from irobot.common.interfaces import RobotController
from irobot.common.domain.skills import SkillContext
from irobot.common.domain.skills.behaviors.approach_target import ApproachTargetSkill
from irobot.common.domain.skills.behaviors.move_circle import MoveCircleSkill
from irobot.common.domain.perception import PerceptionTarget
from tests.unit.fake_robot import FakeRobot



def build_context(fake_robot: FakeRobot | None = None, **state):
    robot = fake_robot or FakeRobot()
    return SkillContext(robot=RobotController(robot), state=state)


def test_approach_target_skill_success_when_target_visible():
    fake = FakeRobot()
    context = build_context(fake, last_ball_position="centre", obstacle_detected=False)

    result = ApproachTargetSkill().execute(context)

    assert result.status == "success"
    assert result.data["target_position"] == "center"
    assert "forward" in fake.commands


def test_approach_target_skill_stops_when_obstacle_detected():
    fake = FakeRobot()
    context = build_context(fake, last_ball_position="centre", obstacle_detected=True)

    result = ApproachTargetSkill().execute(context)

    assert result.status == "success"
    assert result.data["obstacle_detected"] is True
    assert result.next_action == "stop_motion"


def test_approach_target_skill_searches_when_target_missing():
    fake = FakeRobot()
    context = build_context(fake, last_ball_position="UNKNOWN", obstacle_detected=False)

    result = ApproachTargetSkill().execute(context)

    assert result.status == "in_progress"
    assert result.data["target_position"] is None
    assert result.next_action == "detect_object"
    assert "right" in fake.commands


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += max(0.0, seconds)


class ScriptedPerception:
    """Renvoie une détection par appel ; None = cible absente. Répète la dernière valeur.

    Une entrée est (position, distance) ou (position, distance, offset_x).
    """

    def __init__(self, script, clock: FakeClock | None = None, on_call=None) -> None:
        self.script = list(script)
        self.calls = 0

    def detect(self, *, target):
        item = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        if item is None:
            return None
        position, distance, *rest = item
        offset_x = rest[0] if rest else None
        return SimpleNamespace(label=target.value, position=position, distance_cm=distance, offset_x=offset_x)


def live_run(script, clock=None, robot=None, **params):
    clock = clock or FakeClock()
    fake = robot or FakeRobot()
    context = SkillContext(
        robot=RobotController(fake),
        perception=ScriptedPerception(script),
        perception_target=PerceptionTarget.YELLOW_BALL,
        state={"active_intent_parameters": {"alignment_step_s": 0.0, "forward_step_s": 0.0, **params}},
    )
    skill = ApproachTargetSkill(settings=RuntimeSettings(), time_fn=clock.time, sleep_fn=clock.sleep)
    return skill.execute(context), fake, context, clock


def test_approach_target_search_succeeds_after_n_pulses():
    script = [None] * 5 + [("center", 50.0)]
    result, fake, context, _ = live_run(script, max_target_loss_s=0.1, search_timeout_s=30.0, stand_off_cm=100)

    assert result.status == "success"
    assert result.data["close_enough"] is True
    assert fake.commands.count("right") == 5


def test_approach_target_search_exhausted_fails_and_stops():
    result, fake, _, clock = live_run([None], search_timeout_s=2.0)

    assert result.status == "failed"
    assert result.data["target_lost"] is True
    assert fake.commands[-1] == "stop"
    assert clock.now >= 2.0


def test_approach_target_search_uses_search_timeout_not_target_loss_budget():
    # max_target_loss_s = 1 s ne doit plus interrompre une recherche de 5 s.
    script = [None] * 100 + [("center", 50.0)]
    result, _, _, clock = live_run(script, max_target_loss_s=1.0, search_timeout_s=60.0, stand_off_cm=100)

    assert result.status == "success"
    assert clock.now > 1.0


def test_approach_target_aligns_toward_target_side():
    for side in ("left", "right"):
        result, fake, _, _ = live_run([(side, None)] * 2 + [("center", 50.0)], stand_off_cm=100)
        assert result.status == "success"
        assert side in fake.commands
        opposite = "right" if side == "left" else "left"
        assert opposite not in fake.commands


def test_approach_target_search_sweeps_toward_last_known_side():
    script = [("left", None)] + [None] * 10 + [("center", 50.0)]
    result, fake, _, _ = live_run(script, max_target_loss_s=0.1, stand_off_cm=100)

    assert result.status == "success"
    assert "right" not in fake.commands
    assert fake.commands.count("left") >= 2


def test_approach_target_search_defaults_to_right_without_history():
    _, fake, _, _ = live_run([None, ("center", 50.0)], stand_off_cm=100)

    assert "right" in fake.commands and "left" not in fake.commands


def test_approach_target_reaches_stand_off_100cm_with_decreasing_distances():
    distances = [250.0, 200.0, 160.0, 130.0, 118.0, 108.0]
    result, fake, _, _ = live_run([("center", d) for d in distances], stand_off_cm=100)

    assert result.status == "success"
    assert result.data["distance_cm"] == 108.0
    assert fake.commands.count("forward") == 5
    assert fake.commands[-1] == "stop"


def test_approach_target_stand_off_alias_and_priority_and_bounds():
    skill = ApproachTargetSkill(settings=RuntimeSettings())
    assert skill._resolve_stand_off_cm({"stand_off_cm": 100}) == 100.0
    assert skill._resolve_stand_off_cm({"stand_off_cm": 100, "approach_threshold_cm": 60}) == 60.0
    assert skill._resolve_stand_off_cm({"stand_off_cm": 5}) == 30.0
    assert skill._resolve_stand_off_cm({"stand_off_cm": 9999}) == 300.0


def test_approach_target_forward_pulses_shorten_near_stand_off():
    skill = ApproachTargetSkill(settings=RuntimeSettings())
    assert skill._forward_step(0.12, 400.0, 100.0) == 0.12
    assert skill._forward_step(0.12, None, 100.0) == 0.12
    assert skill._forward_step(0.12, 150.0, 100.0) < 0.12


def test_approach_target_turns_only_when_target_out_of_stand_off_band():
    result, fake, _, _ = live_run([("right", 150.0, 0.1)], max_target_loss_s=0.1, max_tracking_s=0.5, stand_off_cm=100)

    assert "right" in fake.commands


def test_approach_target_does_not_turn_when_reached_off_centre():
    result, fake, _, _ = live_run([("right", 80.0, 0.9)], stand_off_cm=100)

    assert result.data["close_enough"] is True
    assert not {"left", "right", "forward"} & set(fake.commands)


def test_approach_target_turns_when_distance_unknown_and_target_off_centre():
    result, fake, _, _ = live_run([("left", None, 0.2)], max_target_loss_s=0.1, max_tracking_s=0.5, stand_off_cm=100)

    assert "left" in fake.commands


def test_approach_target_live_obstacle_stops_safely():
    fake = FakeRobot()
    fake.obstacle_detected = True
    result, fake, _, _ = live_run([("center", 200.0)], robot=fake, stand_off_cm=100)

    assert result.status == "success"
    assert result.data["obstacle_detected"] is True
    assert fake.commands == ["stop"]


def test_approach_target_search_time_does_not_consume_tracking_budget():
    script = [None] * 30 + [("center", 50.0)]
    result, _, _, _ = live_run(script, search_timeout_s=60.0, tracking_timeout_s=1.0, stand_off_cm=100)

    assert result.status == "success"


@pytest.mark.parametrize("live", [False, True])
@pytest.mark.parametrize("target_object", ["marker", "red_ball", "bottle"])
def test_approach_target_uses_same_policy_for_any_target(live, target_object):
    params = {
        "target_object": target_object,
        "stand_off_cm": 100,
        "stand_off_tolerance_cm": 10,
        "alignment_step_s": 0.0,
        "forward_step_s": 0.0,
        "tracking_timeout_s": 0.1,
        "search_timeout_s": 0.1,
    }
    if live:
        result, fake, _, _ = live_run([("center", None)], **params)
    else:
        fake = FakeRobot()
        context = build_context(
            fake,
            target_object=target_object,
            active_intent_parameters=params,
            last_object_position="center",
            last_object_distance_cm=None,
        )
        result = ApproachTargetSkill(settings=RuntimeSettings(), sleep_fn=lambda _: None).execute(context)

    assert "forward" in fake.commands
    assert result.status != "failed"


def test_move_circle_skill_executes_compound_motion():
    fake = FakeRobot()
    context = build_context(fake)

    result = MoveCircleSkill().execute(context)

    assert result.status == "success"
    assert result.data["motion"] == "circle"
    assert fake.commands[0] == "left"
    assert fake.commands[1] == "forward"
