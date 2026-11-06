"""Skills du robot.

Organisation claire :
- primitives : actions atomiques sur les actionneurs
- perception : détection sensorielle
- behaviors : tâches composites
"""

from irobot.common.domain.skills.base_skill import Skill, SkillContext, SkillResult
from irobot.common.domain.skills.behaviors.approach_target import ApproachTargetSkill
from irobot.common.domain.skills.behaviors.follow_object import FollowObjectSkill
from irobot.common.domain.skills.behaviors.move_circle import MoveCircleSkill
from irobot.common.domain.skills.blackboard_state import BlackboardState
from irobot.common.domain.skills.perception.detect_object import DetectObjectSkill
from irobot.common.domain.skills.perception.detect_obstacle import DetectObstacleSkill
from irobot.common.domain.skills.primitives.move_backward import MoveBackwardSkill
from irobot.common.domain.skills.primitives.move_forward import MoveForwardSkill
from irobot.common.domain.skills.primitives.stop_motion import StopMotionSkill
from irobot.common.domain.skills.primitives.turn_left import TurnLeftSkill
from irobot.common.domain.skills.primitives.turn_right import TurnRightSkill

__all__ = [
    "ApproachTargetSkill",
    "BlackboardState",
    "DetectObjectSkill",
    "DetectObstacleSkill",
    "FollowObjectSkill",
    "MoveBackwardSkill",
    "MoveCircleSkill",
    "MoveForwardSkill",
    "Skill",
    "SkillContext",
    "SkillResult",
    "StopMotionSkill",
    "TurnLeftSkill",
    "TurnRightSkill",
]
