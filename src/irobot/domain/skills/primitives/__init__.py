"""Primitives de déplacement du robot.

Ces compétences représentent des actions de base et atomiques que le robot peut
exécuter directement sur le contrôleur de mouvement.
"""

from irobot.domain.skills.primitives.move_forward import MoveForwardSkill
from irobot.domain.skills.primitives.move_backward import MoveBackwardSkill
from irobot.domain.skills.primitives.turn_left import TurnLeftSkill
from irobot.domain.skills.primitives.turn_right import TurnRightSkill
from irobot.domain.skills.primitives.stop_motion import StopMotionSkill

__all__ = [
    "MoveForwardSkill",
    "MoveBackwardSkill",
    "TurnLeftSkill",
    "TurnRightSkill",
    "StopMotionSkill",
]
