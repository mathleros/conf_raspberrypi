from __future__ import annotations

from irobot.domain.skills.primitives.base_motion_primitive import BaseMotionPrimitiveSkill


class MoveForwardSkill(BaseMotionPrimitiveSkill):
    """Skill primitive : avance le robot en ligne droite."""

    name = "move_forward"
    description = "Avance le robot en ligne droite à la vitesse courante"
    motion = "forward"
    command_method = "forward"
    command_for_method = "forward_for"
    parameter_mode = "distance"
    success_message = "Le robot avance."
    failure_message = "Le robot ne fournit pas de méthode forward()"
    error_prefix = "Erreur lors du déplacement avant"
