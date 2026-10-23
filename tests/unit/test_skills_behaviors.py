from __future__ import annotations

from irobot.robot_controller import RobotController
from irobot.skills import SkillContext
from irobot.skills.behaviors.follow_target import FollowTargetSkill
from irobot.skills.behaviors.move_circle import MoveCircleSkill
from tests.unit.fake_robot import FakeRobot


def build_context(fake_robot: FakeRobot | None = None, **state):
    robot = fake_robot or FakeRobot()
    return SkillContext(robot=RobotController(robot), state=state)


def test_follow_target_skill_success_when_target_visible():
    fake = FakeRobot()
    context = build_context(fake, last_ball_position="centre", obstacle_detected=False)

    result = FollowTargetSkill().execute(context)

    assert result.status == "success"
    assert result.data["target_position"] == "centre"
    assert fake.commands[-1] == "forward"


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

    assert result.status == "failed"
    assert result.data["target_position"] is None
    assert result.next_action == "stop_motion"


def test_move_circle_skill_executes_compound_motion():
    fake = FakeRobot()
    context = build_context(fake)

    result = MoveCircleSkill().execute(context)

    assert result.status == "success"
    assert result.data["motion"] == "circle"
    assert fake.commands[0] == "left"
    assert fake.commands[1] == "forward"
