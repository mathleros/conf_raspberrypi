from __future__ import annotations

"""Skill de rotation gauche.

Cette skill s'appuie sur la primitive de déplacement du robot existant pour
appliquer une rotation vers la gauche.
"""

from irobot.skills.base_skill import Skill, SkillContext, SkillResult


class TurnLeftSkill(Skill):
    """Tourne le robot vers la gauche."""

    name = "turn_left"
    description = "Tourne le robot vers la gauche à la vitesse courante"

    def validate(self, context: SkillContext) -> bool:
        return context.robot is not None

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            if hasattr(context.robot, "left"):
                context.robot.left()
            else:
                return SkillResult(
                    status="failed",
                    message="Le robot ne fournit pas de méthode left()",
                    data={"skill": self.name},
                    confidence=0.0,
                    next_action=None,
                )

            context.state["motion"] = "left"
            return SkillResult(
                status="success",
                message="Rotation gauche exécutée.",
                data={"motion": "left"},
                confidence=0.9,
                next_action="track_target",
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors de la rotation gauche : {exc}",
                data={"error": str(exc), "skill": self.name},
                confidence=0.0,
                next_action=None,
            )
