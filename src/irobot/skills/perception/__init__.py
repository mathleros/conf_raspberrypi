"""Skills de perception du robot.

Ce sous-package regroupe les compétences qui lisent l'environnement du robot :
vision, détection d'objet, détection d'obstacle, lecture de distance.
"""

from irobot.skills.perception.detect_obstacle import DetectObstacleSkill
from irobot.skills.perception.detect_red_ball import DetectRedBallSkill

__all__ = [
    "DetectRedBallSkill",
    "DetectObstacleSkill",
]
