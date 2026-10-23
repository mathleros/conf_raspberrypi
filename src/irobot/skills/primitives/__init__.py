"""Skills primitives du robot.

Ce sous-package regroupe les actions atomiques directement exécutables sur les
actionneurs : avance, recul, rotation, arrêt.
"""

from irobot.skills.primitives.move_backward import MoveBackwardSkill
from irobot.skills.primitives.move_forward import MoveForwardSkill
from irobot.skills.primitives.stop_motion import StopMotionSkill
from irobot.skills.primitives.turn_left import TurnLeftSkill
from irobot.skills.primitives.turn_right import TurnRightSkill

__all__ = [
    "MoveForwardSkill",
    "MoveBackwardSkill",
    "TurnLeftSkill",
    "TurnRightSkill",
    "StopMotionSkill",
]
