from __future__ import annotations

from irobot.robot_controller import RobotController
from irobot.skills import SkillContext
from irobot.skills.primitives.move_backward import MoveBackwardSkill
from irobot.skills.primitives.move_forward import MoveForwardSkill
from irobot.skills.primitives.stop_motion import StopMotionSkill
from irobot.skills.primitives.turn_left import TurnLeftSkill
from irobot.skills.primitives.turn_right import TurnRightSkill
from tests.unit.fake_robot import FakeRobot


def build_context(fake_robot: FakeRobot | None = None) -> SkillContext:
    robot = fake_robot or FakeRobot()
    return SkillContext(robot=RobotController(robot), state={})


def test_move_forward_skill_executes_forward_command():
    fake = FakeRobot()
    context = build_context(fake)

    result = MoveForwardSkill().execute(context)

    assert result.status == "success"
    assert result.data["motion"] == "forward"
    assert fake.commands[-1] == "forward"


def test_move_backward_skill_executes_backward_command():
    fake = FakeRobot()
    context = build_context(fake)

    result = MoveBackwardSkill().execute(context)

    assert result.status == "success"
    assert result.data["motion"] == "backward"
    assert fake.commands[-1] == "backward"


def test_turn_left_skill_executes_turn_left_command():
    fake = FakeRobot()
    context = build_context(fake)

    result = TurnLeftSkill().execute(context)

    assert result.status == "success"
    assert result.data["motion"] == "left"
    assert fake.commands[-1] == "left"


def test_turn_right_skill_executes_turn_right_command():
    fake = FakeRobot()
    context = build_context(fake)

    result = TurnRightSkill().execute(context)

    assert result.status == "success"
    assert result.data["motion"] == "right"
    assert fake.commands[-1] == "right"


def test_stop_motion_skill_executes_stop_command():
    fake = FakeRobot()
    context = build_context(fake)

    result = StopMotionSkill().execute(context)

    assert result.status == "success"
    assert result.data["motion"] == "stop"
    assert fake.commands[-1] == "stop"


def test_skill_validation_requires_robot_context():
    skill = MoveForwardSkill()

    assert skill.validate(SkillContext(robot=None, state={})) is False
    assert skill.validate(build_context()) is True
