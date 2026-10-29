import pytest

from irobot.config.settings import RuntimeSettings
from irobot.domain.skills import SkillContext
from irobot.domain.skills.behaviors.follow_object import FollowObjectSkill
from irobot.domain.skills.primitives import base_motion_primitive
from irobot.domain.skills.primitives.move_backward import MoveBackwardSkill
from irobot.domain.skills.primitives.move_forward import MoveForwardSkill
from irobot.domain.skills.primitives.turn_left import TurnLeftSkill
from irobot.domain.skills.primitives.turn_right import TurnRightSkill


@pytest.mark.parametrize(
    ("skill", "parameters", "expected"),
    [
        (MoveForwardSkill(), {"distance": 20}, 20 / 55),
        (MoveBackwardSkill(), {"distance": 10}, 10 / 25),
        (MoveBackwardSkill(), {"distance": 0.1, "unit": "m"}, 10 / 25),
        (MoveBackwardSkill(), {"duration": 1}, 1),
        (TurnLeftSkill(), {"angle": 45}, 0.25),
        (TurnRightSkill(), {"angle": 90}, 0.5),
    ],
)
def test_directional_motion_duration(monkeypatch, skill, parameters, expected):
    settings = RuntimeSettings(cm_per_second=55, backward_cm_per_second=25, deg_per_second=180)
    monkeypatch.setattr(base_motion_primitive, "SETTINGS", settings)
    context = SkillContext(state={"active_intent_parameters": parameters})

    assert skill._resolve_motion_parameters(context)["duration"] == pytest.approx(expected)


def test_missing_backward_calibration_preserves_shared_speed(monkeypatch):
    monkeypatch.setattr(base_motion_primitive, "SETTINGS", RuntimeSettings(cm_per_second=50))
    context = SkillContext(state={"active_intent_parameters": {"distance": 10}})

    assert MoveBackwardSkill()._resolve_motion_parameters(context)["duration"] == pytest.approx(0.2)


def test_follow_uses_directional_speed_and_preserves_pulse_limits():
    skill = FollowObjectSkill(settings=RuntimeSettings(cm_per_second=55, backward_cm_per_second=25))

    assert skill._step(3, 0.05, 0.25) == pytest.approx(3 / 55)
    assert skill._step(3, 0.05, 0.15, backward=True) == pytest.approx(0.12)
    assert skill._step(100, 0.05, 0.15, backward=True) == 0.15
