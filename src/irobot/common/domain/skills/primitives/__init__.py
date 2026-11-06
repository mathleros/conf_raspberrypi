"""Primitives de déplacement du robot.

Ces compétences représentent des actions de base et atomiques que le robot peut
exécuter directement sur le contrôleur de mouvement.
"""

from irobot.common.domain.skills.primitives.base_motion_primitive import (
    BaseMotionPrimitiveSkill,
)
from irobot.common.domain.skills.primitives.move_backward import MoveBackwardSkill
from irobot.common.domain.skills.primitives.move_forward import MoveForwardSkill
from irobot.common.domain.skills.primitives.stop_motion import StopMotionSkill
from irobot.common.domain.skills.primitives.turn_left import TurnLeftSkill
from irobot.common.domain.skills.primitives.turn_right import TurnRightSkill

__all__ = [
    "BaseMotionPrimitiveSkill",
    "MoveBackwardSkill",
    "MoveForwardSkill",
    "StopMotionSkill",
    "TurnLeftSkill",
    "TurnRightSkill",
]
