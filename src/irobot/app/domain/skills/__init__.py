"""Skills du robot.

Organisation claire :
- primitives : actions atomiques sur les actionneurs
- perception : détection sensorielle
- behaviors : tâches composites
"""

from irobot.app.domain.skills.base_skill import Skill, SkillContext, SkillResult
from irobot.app.domain.skills.behaviors.approach_target import ApproachTargetSkill
from irobot.app.domain.skills.behaviors.follow_object import FollowObjectSkill
from irobot.app.domain.skills.behaviors.move_circle import MoveCircleSkill
from irobot.app.domain.skills.blackboard_state import BlackboardState
from irobot.app.domain.skills.perception.detect_object import DetectObjectSkill
from irobot.app.domain.skills.perception.detect_obstacle import DetectObstacleSkill
from irobot.app.domain.skills.primitives.move_backward import MoveBackwardSkill
from irobot.app.domain.skills.primitives.move_forward import MoveForwardSkill
from irobot.app.domain.skills.primitives.stop_motion import StopMotionSkill
from irobot.app.domain.skills.primitives.turn_left import TurnLeftSkill
from irobot.app.domain.skills.primitives.turn_right import TurnRightSkill

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
