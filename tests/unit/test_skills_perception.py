from __future__ import annotations

from irobot.robot_controller import RobotController
from irobot.skills import SkillContext
from irobot.skills.perception.detect_obstacle import DetectObstacleSkill
from irobot.skills.perception.detect_red_ball import DetectRedBallSkill
from tests.unit.fake_robot import FakeRobot


def build_context(fake_robot: FakeRobot | None = None, **state):
    robot = fake_robot or FakeRobot()
    return SkillContext(robot=RobotController(robot), state=state)


def test_detect_red_ball_skill_success_when_target_present():
    context = build_context(last_ball_position="centre")

    result = DetectRedBallSkill().execute(context)

    assert result.status == "success"
    assert result.data["position"] == "centre"
    assert result.next_action == "align_to_target"


def test_detect_red_ball_skill_failed_when_target_missing():
    context = build_context(last_ball_position="UNKNOWN")

    result = DetectRedBallSkill().execute(context)

    assert result.status == "failed"
    assert result.data["position"] is None
    assert result.next_action == "scan_for_target"


def test_detect_obstacle_skill_success_when_no_obstacle():
    fake = FakeRobot()
    fake.obstacle_detected = False
    context = build_context(fake)

    result = DetectObstacleSkill().execute(context)

    assert result.status == "success"
    assert result.data["obstacle_detected"] is False
    assert result.next_action == "track_target"


def test_detect_obstacle_skill_success_when_obstacle_detected():
    fake = FakeRobot()
    fake.obstacle_detected = True
    context = build_context(fake)

    result = DetectObstacleSkill().execute(context)

    assert result.status == "success"
    assert result.data["obstacle_detected"] is True
    assert result.next_action == "stop_motion"
