from __future__ import annotations

"""Skill de trajectoire circulaire.

Cette skill ne fait pas un calcul de contrôle avancé, mais formalise le type de
commande de mouvement nécessaire pour réaliser un rond ou une trajectoire
circulaire, dans le cadre d'un système de planification robotique.
"""

from irobot.skills.base_skill import Skill, SkillContext, SkillResult


class MoveCircleSkill(Skill):
    """Pilote une trajectoire circulaire / en rond."""

    name = "move_circle"
    description = "Réalise une trajectoire circulaire de manière contrôlée"

    def validate(self, context: SkillContext) -> bool:
        return context.robot is not None

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            if hasattr(context.robot, "left") and hasattr(context.robot, "forward"):
                context.robot.left()
                context.robot.forward()
            else:
                return SkillResult(
                    status="failed",
                    message="Le robot ne fournit pas les méthodes nécessaires pour un mouvement circulaire.",
                    data={"skill": self.name},
                    confidence=0.0,
                    next_action=None,
                )

            context.state["motion"] = "circle"
            return SkillResult(
                status="success",
                message="Mouvement circulaire en cours.",
                data={"motion": "circle"},
                confidence=0.8,
                next_action="stop_motion",
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors du mouvement circulaire : {exc}",
                data={"error": str(exc), "skill": self.name},
                confidence=0.0,
                next_action=None,
            )
