"""Skills du robot.

Organisation claire et visible :
- primitives : actions atomiques du robot
- perception : détection et lecture de capteurs
- behaviors : tâches composites construites à partir des primitives
"""

from irobot.skills.base_skill import Skill, SkillContext, SkillResult
from irobot.skills.behaviors.follow_target import FollowTargetSkill
from irobot.skills.behaviors.move_circle import MoveCircleSkill
from irobot.skills.perception.detect_obstacle import DetectObstacleSkill
from irobot.skills.perception.detect_red_ball import DetectRedBallSkill
from irobot.skills.primitives.move_backward import MoveBackwardSkill
from irobot.skills.primitives.move_forward import MoveForwardSkill
from irobot.skills.primitives.stop_motion import StopMotionSkill
from irobot.skills.primitives.turn_left import TurnLeftSkill
from irobot.skills.primitives.turn_right import TurnRightSkill

__all__ = [
    "Skill",
    "SkillContext",
    "SkillResult",
    "MoveForwardSkill",
    "MoveBackwardSkill",
    "TurnLeftSkill",
    "TurnRightSkill",
    "StopMotionSkill",
    "DetectRedBallSkill",
    "DetectObstacleSkill",
    "FollowTargetSkill",
    "MoveCircleSkill",
]
