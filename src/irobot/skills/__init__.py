"""Skills du robot.

Ce package expose le contrat de base pour toutes les compétences unitaires du
robot, ainsi que quelques skills de référence à intégrer progressivement.
"""

from irobot.skills.base_skill import Skill, SkillContext, SkillResult
from irobot.skills.detect_obstacle import DetectObstacleSkill
from irobot.skills.detect_red_ball import DetectRedBallSkill
from irobot.skills.follow_target import FollowTargetSkill
from irobot.skills.move_circle import MoveCircleSkill
from irobot.skills.move_forward import MoveForwardSkill
from irobot.skills.stop_motion import StopMotionSkill
from irobot.skills.turn_left import TurnLeftSkill
from irobot.skills.turn_right import TurnRightSkill

__all__ = [
    "Skill",
    "SkillContext",
    "SkillResult",
    "MoveForwardSkill",
    "TurnLeftSkill",
    "TurnRightSkill",
    "StopMotionSkill",
    "DetectRedBallSkill",
    "DetectObstacleSkill",
    "FollowTargetSkill",
    "MoveCircleSkill",
]
