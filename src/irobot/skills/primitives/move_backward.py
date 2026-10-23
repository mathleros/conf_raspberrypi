from __future__ import annotations

from irobot.skills.base_skill import Skill, SkillContext, SkillResult


class MoveBackwardSkill(Skill):
    """Skill primitive : recule le robot en ligne droite."""

    name = "move_backward"
    description = "Recule le robot en ligne droite à la vitesse courante"

    def validate(self, context: SkillContext) -> bool:
        return context.robot is not None

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            if hasattr(context.robot, "backward"):
                context.robot.backward()
            else:
                return SkillResult(
                    status="failed",
                    message="Le robot ne fournit pas de méthode backward()",
                    data={"skill": self.name},
                    confidence=0.0,
                    next_action=None,
                )

            context.state["motion"] = "backward"
            return SkillResult(
                status="success",
                message="Le robot recule.",
                data={"motion": "backward"},
                confidence=1.0,
                next_action="track_target",
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors du recul : {exc}",
                data={"error": str(exc), "skill": self.name},
                confidence=0.0,
                next_action=None,
            )
