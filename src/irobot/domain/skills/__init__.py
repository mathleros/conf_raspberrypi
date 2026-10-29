"""Skills du robot.

Organisation claire :
- primitives : actions atomiques sur les actionneurs
- perception : détection sensorielle
- behaviors : tâches composites
"""

from irobot.domain.skills.base_skill import Skill, SkillContext, SkillResult
from irobot.domain.skills.blackboard_state import BlackboardState
from irobot.domain.skills.behaviors.follow_object import FollowObjectSkill
from irobot.domain.skills.behaviors.follow_target import FollowTargetSkill
from irobot.domain.skills.behaviors.move_circle import MoveCircleSkill
from irobot.domain.skills.perception.detect_object import DetectObjectSkill
from irobot.domain.skills.perception.detect_obstacle import DetectObstacleSkill
from irobot.domain.skills.primitives.move_backward import MoveBackwardSkill
from irobot.domain.skills.primitives.move_forward import MoveForwardSkill
from irobot.domain.skills.primitives.stop_motion import StopMotionSkill
from irobot.domain.skills.primitives.turn_left import TurnLeftSkill
from irobot.domain.skills.primitives.turn_right import TurnRightSkill

__all__ = [
    "Skill",
    "SkillContext",
    "SkillResult",
    "BlackboardState",
    "MoveForwardSkill",
    "MoveBackwardSkill",
    "TurnLeftSkill",
    "TurnRightSkill",
    "StopMotionSkill",
    "DetectObjectSkill",
    "DetectObstacleSkill",
    "FollowObjectSkill",
    "FollowTargetSkill",
    "MoveCircleSkill",
]
