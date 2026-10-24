from __future__ import annotations

from irobot.domain.skills.primitives.base_motion_primitive import BaseMotionPrimitiveSkill


class MoveBackwardSkill(BaseMotionPrimitiveSkill):
    """Skill primitive : recule le robot en ligne droite."""

    name = "move_backward"
    description = "Recule le robot en ligne droite à la vitesse courante"
    motion = "backward"
    command_method = "backward"
    command_for_method = "backward_for"
    parameter_mode = "distance"
    success_message = "Le robot recule."
    failure_message = "Le robot ne fournit pas de méthode backward()"
    error_prefix = "Erreur lors du recul"
