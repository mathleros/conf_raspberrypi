from __future__ import annotations

from irobot.domain.skills.primitives.base_motion_primitive import BaseMotionPrimitiveSkill


class TurnLeftSkill(BaseMotionPrimitiveSkill):
    """Skill primitive : tourne le robot vers la gauche."""

    name = "turn_left"
    description = "Tourne le robot vers la gauche à la vitesse courante"
    motion = "left"
    command_method = "left"
    command_for_method = "left_for"
    parameter_mode = "angle"
    success_message = "Rotation gauche exécutée."
    failure_message = "Le robot ne fournit pas de méthode left()"
    error_prefix = "Erreur lors de la rotation gauche"
