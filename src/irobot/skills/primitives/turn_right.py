from __future__ import annotations

from irobot.skills.base_skill import Skill, SkillContext, SkillResult


class TurnRightSkill(Skill):
    """Skill primitive : tourne le robot vers la droite."""

    name = "turn_right"
    description = "Tourne le robot vers la droite à la vitesse courante"

    def validate(self, context: SkillContext) -> bool:
        return context.robot is not None

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            if hasattr(context.robot, "right"):
                context.robot.right()
            else:
                return SkillResult(
                    status="failed",
                    message="Le robot ne fournit pas de méthode right()",
                    data={"skill": self.name},
                    confidence=0.0,
                    next_action=None,
                )

            context.state["motion"] = "right"
            return SkillResult(
                status="success",
                message="Rotation droite exécutée.",
                data={"motion": "right"},
                confidence=0.9,
                next_action="track_target",
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors de la rotation droite : {exc}",
                data={"error": str(exc), "skill": self.name},
                confidence=0.0,
                next_action=None,
            )
