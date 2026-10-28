from __future__ import annotations

from types import SimpleNamespace

import pytest

from irobot.config.settings import RuntimeSettings
from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.domain.skills import SkillContext
from irobot.domain.skills.behaviors.follow_object import FollowObjectSkill
from tests.unit.fake_robot import FakeRobot


class World(FakeRobot):
    """Robot + perception simulés avec horloge : la balle bouge selon les impulsions."""

    def __init__(self, distance_cm=100.0, drift_cm_s=0.0, hidden=None, bearing="center"):
        super().__init__()
        self.now = 0.0
        self.distance_cm = distance_cm
        self.drift_cm_s = drift_cm_s
        self.hidden = hidden or (0.0, 0.0)
        self.bearing = bearing
        self.emergency = False
        self.detect_error: Exception | None = None

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds
        self.distance_cm += self.drift_cm_s * seconds

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
        self.bearing = "center"
        self.sleep(duration)

    def right_for(self, duration: float) -> None:
        self.commands.append("right")
        self.bearing = "center"
        self.sleep(duration)

    def is_emergency_stop_requested(self) -> bool:
        return self.emergency

    def detect(self, target=None):
        if self.detect_error:
            raise self.detect_error
        if self.hidden[0] <= self.now < self.hidden[1]:
            return None
        return SimpleNamespace(label=target, position=self.bearing, distance_cm=self.distance_cm)


def run(world: World, **params):
    context = SkillContext(robot=world, perception=world, state={"active_intent_parameters": params})
    skill = FollowObjectSkill(settings=RuntimeSettings(), time_fn=world.time, sleep_fn=world.sleep)
    return skill.execute(context), context


MOTIONS = {"forward", "backward", "left", "right"}


def test_registered_in_default_registry():
    assert "follow_object" in SkillRegistry.default()


def test_holds_distance_in_dead_zone_without_moving():
    world = World(distance_cm=110.0)
    result, context = run(world, duration_s=5)

    assert result.status == "success"
    assert not MOTIONS & set(world.commands)
    assert result.data["final_distance_cm"] == 110.0
    assert result.data["reacquisitions"] == 0
    assert result.data["iterations"] > 0
    assert context.state["follow_target_state"]["phase"] == "holding"
    assert world.commands[-1] == "stop"


def test_approaches_when_too_far():
    world = World(distance_cm=200.0)
    result, _ = run(world, duration_s=30)

    assert "forward" in world.commands
    assert "backward" not in world.commands
    assert 85.0 <= result.data["final_distance_cm"] <= 115.0


def test_backs_up_when_too_close():
    world = World(distance_cm=50.0)
    result, _ = run(world, duration_s=30)

    assert "backward" in world.commands
    assert "forward" not in world.commands
    assert 85.0 <= result.data["final_distance_cm"] <= 115.0


def test_follows_receding_ball():
    world = World(distance_cm=100.0, drift_cm_s=5.0)
    result, _ = run(world, duration_s=20)

    assert "forward" in world.commands
    assert result.data["final_distance_cm"] <= 120.0


def test_aligns_before_regulating_distance():
    world = World(distance_cm=200.0, bearing="left")
    run(world, duration_s=1)

    assert world.commands[0] == "left"
    assert "forward" in world.commands


def test_target_lost_briefly_stops_without_search():
    world = World(distance_cm=100.0, hidden=(1.0, 2.0))
    result, _ = run(world, duration_s=6, max_target_loss_s=3.0)

    assert result.status == "success"
    assert not {"left", "right"} & set(world.commands)
    assert result.data["reacquisitions"] == 0


def test_target_lost_then_reacquired():
    world = World(distance_cm=100.0, hidden=(1.0, 8.0))
    result, _ = run(world, duration_s=20, max_target_loss_s=1.0, search_timeout_s=30)

    assert result.status == "success"
    assert "right" in world.commands
    assert result.data["reacquisitions"] == 1


def test_target_permanently_lost_fails():
    world = World(distance_cm=100.0, hidden=(0.0, 1e9))
    result, context = run(world, duration_s=600, max_target_loss_s=1.0, search_timeout_s=5)

    assert result.status == "failed"
    assert result.data["target_lost"] is True
    assert world.commands[-1] == "stop"
    assert context.state["follow_target_state"]["phase"] == "lost_target"


def test_obstacle_stops_with_success():
    world = World(distance_cm=200.0)
    world.obstacle_detected = True
    result, _ = run(world, duration_s=10)

    assert result.status == "success"
    assert result.data["obstacle_detected"] is True
    assert not MOTIONS & set(world.commands)
    assert world.commands[-1] == "stop"


def test_emergency_stop_halts_following():
    world = World(distance_cm=200.0)
    world.emergency = True
    result, _ = run(world, duration_s=10)

    assert result.data["obstacle_detected"] is True
    assert result.data["emergency_stop"] is True
    assert not MOTIONS & set(world.commands)


def test_ends_at_duration():
    world = World(distance_cm=100.0)
    result, _ = run(world, duration_s=3)

    assert result.status == "success"
    assert result.data["duration_s"] == 3
    assert 3.0 <= world.now < 3.1


def test_duration_is_capped_by_settings():
    world = World(distance_cm=100.0)
    context = SkillContext(robot=world, perception=world, state={"active_intent_parameters": {"duration_s": 5000}})
    settings = RuntimeSettings(max_follow_duration_sec=2.0)
    result = FollowObjectSkill(settings=settings, time_fn=world.time, sleep_fn=world.sleep).execute(context)

    assert result.data["duration_s"] == 2.0


def test_stop_guaranteed_on_exception():
    world = World(distance_cm=100.0)
    world.detect_error = RuntimeError("camera down")
    result, _ = run(world, duration_s=5)

    assert result.status == "failed"
    assert "camera down" in result.data["error"]
    assert world.commands[-1] == "stop"


@pytest.mark.parametrize("raw,expected", [(10, 30.0), (9999, 300.0), (100, 100.0)])
def test_stand_off_is_clamped(raw, expected):
    world = World(distance_cm=expected)
    result, _ = run(world, duration_s=1, stand_off_cm=raw)

    assert not MOTIONS & set(world.commands)
    assert result.status == "success"
