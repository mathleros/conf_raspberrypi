from __future__ import annotations

from irobot.domain.skills.primitives.base_motion_primitive import BaseMotionPrimitiveSkill


class TurnRightSkill(BaseMotionPrimitiveSkill):
    """Skill primitive : tourne le robot vers la droite."""

    name = "turn_right"
    description = "Tourne le robot vers la droite à la vitesse courante"
    motion = "right"
    command_method = "right"
    command_for_method = "right_for"
    parameter_mode = "angle"
    success_message = "Rotation droite exécutée."
    failure_message = "Le robot ne fournit pas de méthode right()"
    error_prefix = "Erreur lors de la rotation droite"
