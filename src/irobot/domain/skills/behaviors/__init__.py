"""Behaviors composites du robot.

Ce sous-package regroupe les tâches plus complexes, construites à partir de
skills primitives et de compétences de perception.
"""

from irobot.domain.skills.behaviors.follow_target import FollowTargetSkill
from irobot.domain.skills.behaviors.move_circle import MoveCircleSkill

__all__ = [
    "FollowTargetSkill",
    "MoveCircleSkill",
]
