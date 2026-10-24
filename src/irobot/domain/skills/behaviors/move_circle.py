from __future__ import annotations

from irobot.domain.skills.base_skill import Skill, SkillContext, SkillResult


class MoveCircleSkill(Skill):
    """Behavior composite : réalise une trajectoire circulaire.

    Ce behavior doit être décomposé en primitives de mouvement (rotation + avance)
    et non exécuté comme une primitive à part entière.
    """

    name = "move_circle"
    description = "Réalise une trajectoire circulaire en combinant rotation et avance"

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
