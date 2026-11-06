"""Skills de perception du robot.

Ce sous-package regroupe les compétences qui lisent l'environnement du robot :
vision, détection d'objet, détection d'obstacle, lecture de distance.
"""

from irobot.common.domain.skills.perception.detect_object import DetectObjectSkill
from irobot.common.domain.skills.perception.detect_obstacle import DetectObstacleSkill

__all__ = [
    "DetectObjectSkill",
    "DetectObstacleSkill",
]
