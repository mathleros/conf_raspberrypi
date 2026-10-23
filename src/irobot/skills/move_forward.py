from __future__ import annotations

from irobot.skills.base_skill import Skill, SkillContext, SkillResult


class MoveForwardSkill(Skill):
    """Fait avancer le robot en ligne droite."""

    name = "move_forward"
    description = "Avance le robot en ligne droite à la vitesse courante"

    def validate(self, context: SkillContext) -> bool:
        return context.robot is not None

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            if hasattr(context.robot, "forward"):
                context.robot.forward()
            else:
                return SkillResult(
                    status="failed",
                    message="Le robot ne fournit pas de méthode forward()",
                    data={},
                    confidence=0.0,
                    next_action=None,
                )

            context.state["motion"] = "forward"
            return SkillResult(
                status="success",
                message="Le robot avance.",
                data={"motion": "forward"},
                confidence=1.0,
                next_action="track_target",
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors du déplacement avant : {exc}",
                data={"error": str(exc)},
                confidence=0.0,
                next_action=None,
            )
