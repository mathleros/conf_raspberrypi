from __future__ import annotations

from types import SimpleNamespace

from irobot.config.settings import RuntimeSettings
from irobot.interfaces import RobotController
from irobot.domain.skills import SkillContext
from irobot.domain.skills.behaviors.follow_target import FollowTargetSkill
from irobot.domain.skills.behaviors.move_circle import MoveCircleSkill
from tests.unit.fake_robot import FakeRobot


def build_context(fake_robot: FakeRobot | None = None, **state):
    robot = fake_robot or FakeRobot()
    return SkillContext(robot=RobotController(robot), state=state)


def test_follow_target_skill_success_when_target_visible():
    fake = FakeRobot()
    context = build_context(fake, last_ball_position="centre", obstacle_detected=False)

    result = FollowTargetSkill().execute(context)

    assert result.status == "success"
    assert result.data["target_position"] == "center"
    assert "forward" in fake.commands


def test_follow_target_skill_stops_when_obstacle_detected():
    fake = FakeRobot()
    context = build_context(fake, last_ball_position="centre", obstacle_detected=True)

    result = FollowTargetSkill().execute(context)

    assert result.status == "success"
    assert result.data["obstacle_detected"] is True
    assert result.next_action == "stop_motion"


def test_follow_target_skill_fails_when_target_missing():
    fake = FakeRobot()
    context = build_context(fake, last_ball_position="UNKNOWN", obstacle_detected=False)

    result = FollowTargetSkill().execute(context)

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
    """Renvoie une détection par appel ; None = cible absente. Répète la dernière valeur."""

    def __init__(self, script, clock: FakeClock | None = None, on_call=None) -> None:
        self.script = list(script)
        self.calls = 0

    def detect(self, target=None):
        item = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        if item is None:
            return None
        position, distance = item
        return SimpleNamespace(label=target, position=position, distance_cm=distance)


def live_run(script, clock=None, robot=None, **params):
    clock = clock or FakeClock()
    fake = robot or FakeRobot()
    context = SkillContext(
        robot=RobotController(fake),
        perception=ScriptedPerception(script),
        state={"active_intent_parameters": {"alignment_step_s": 0.0, "forward_step_s": 0.0, **params}},
    )
    skill = FollowTargetSkill(settings=RuntimeSettings(), time_fn=clock.time, sleep_fn=clock.sleep)
    return skill.execute(context), fake, context, clock


def test_follow_target_search_succeeds_after_n_pulses():
    script = [None] * 5 + [("center", 50.0)]
    result, fake, context, _ = live_run(script, max_target_loss_s=0.1, search_timeout_s=30.0, stand_off_cm=100)

    assert result.status == "success"
    assert result.data["close_enough"] is True
    assert fake.commands.count("right") == 5


def test_follow_target_search_exhausted_fails_and_stops():
    result, fake, _, clock = live_run([None], search_timeout_s=2.0)

    assert result.status == "failed"
    assert result.data["target_lost"] is True
    assert fake.commands[-1] == "stop"
    assert clock.now >= 2.0


def test_follow_target_search_uses_search_timeout_not_target_loss_budget():
    # max_target_loss_s = 1 s ne doit plus interrompre une recherche de 5 s.
    script = [None] * 100 + [("center", 50.0)]
    result, _, _, clock = live_run(script, max_target_loss_s=1.0, search_timeout_s=60.0, stand_off_cm=100)

    assert result.status == "success"
    assert clock.now > 1.0


def test_follow_target_aligns_toward_target_side():
    for side in ("left", "right"):
        result, fake, _, _ = live_run([(side, None)] * 2 + [("center", 50.0)], stand_off_cm=100)
        assert result.status == "success"
        assert side in fake.commands
        opposite = "right" if side == "left" else "left"
        assert opposite not in fake.commands


def test_follow_target_search_sweeps_toward_last_known_side():
    script = [("left", None)] + [None] * 10 + [("center", 50.0)]
    result, fake, _, _ = live_run(script, max_target_loss_s=0.1, stand_off_cm=100)

    assert result.status == "success"
    assert "right" not in fake.commands
    assert fake.commands.count("left") >= 2


def test_follow_target_search_defaults_to_right_without_history():
    _, fake, _, _ = live_run([None, ("center", 50.0)], stand_off_cm=100)

    assert "right" in fake.commands and "left" not in fake.commands


def test_follow_target_reaches_stand_off_100cm_with_decreasing_distances():
    distances = [250.0, 200.0, 160.0, 130.0, 118.0, 108.0]
    result, fake, _, _ = live_run([("center", d) for d in distances], stand_off_cm=100)

    assert result.status == "success"
    assert result.data["distance_cm"] == 108.0
    assert fake.commands.count("forward") == 5
    assert fake.commands[-1] == "stop"


def test_follow_target_stand_off_alias_and_priority_and_bounds():
    skill = FollowTargetSkill(settings=RuntimeSettings())
    assert skill._resolve_stand_off_cm({"stand_off_cm": 100}) == 100.0
    assert skill._resolve_stand_off_cm({"stand_off_cm": 100, "approach_threshold_cm": 60}) == 60.0
    assert skill._resolve_stand_off_cm({"stand_off_cm": 5}) == 30.0
    assert skill._resolve_stand_off_cm({"stand_off_cm": 9999}) == 300.0


def test_follow_target_forward_pulses_shorten_near_stand_off():
    skill = FollowTargetSkill(settings=RuntimeSettings())
    assert skill._forward_step(0.12, 400.0, 100.0) == 0.12
    assert skill._forward_step(0.12, None, 100.0) == 0.12
    assert skill._forward_step(0.12, 150.0, 100.0) < 0.12


def test_follow_target_live_obstacle_stops_safely():
    fake = FakeRobot()
    fake.obstacle_detected = True
    result, fake, _, _ = live_run([("center", 200.0)], robot=fake, stand_off_cm=100)

    assert result.status == "success"
    assert result.data["obstacle_detected"] is True
    assert fake.commands == ["stop"]


def test_follow_target_search_time_does_not_consume_tracking_budget():
    script = [None] * 30 + [("center", 50.0)]
    result, _, _, _ = live_run(script, search_timeout_s=60.0, tracking_timeout_s=1.0, stand_off_cm=100)

    assert result.status == "success"


def test_move_circle_skill_executes_compound_motion():
    fake = FakeRobot()
    context = build_context(fake)

    result = MoveCircleSkill().execute(context)

    assert result.status == "success"
    assert result.data["motion"] == "circle"
    assert fake.commands[0] == "left"
    assert fake.commands[1] == "forward"
