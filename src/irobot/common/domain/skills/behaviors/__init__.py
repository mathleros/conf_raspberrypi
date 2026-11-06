"""Behaviors composites du robot.

Ce sous-package regroupe les tâches plus complexes, construites à partir de
skills primitives et de compétences de perception.
"""

from irobot.common.domain.skills.behaviors.approach_target import ApproachTargetSkill
from irobot.common.domain.skills.behaviors.follow_object import FollowObjectSkill
from irobot.common.domain.skills.behaviors.move_circle import MoveCircleSkill

__all__ = [
    "ApproachTargetSkill",
    "FollowObjectSkill",
    "MoveCircleSkill",
]
