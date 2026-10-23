from __future__ import annotations

from irobot.skills.base_skill import Skill, SkillContext, SkillResult


class StopMotionSkill(Skill):
    """Arrête immédiatement le robot."""

    name = "stop_motion"
    description = "Met le robot à l'arrêt et annule les mouvements en cours"

    def validate(self, context: SkillContext) -> bool:
        return context.robot is not None

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            if hasattr(context.robot, "stop"):
                context.robot.stop()
            else:
                return SkillResult(
                    status="failed",
                    message="Le robot ne fournit pas de méthode stop()",
                    data={},
                    confidence=0.0,
                    next_action=None,
                )

            context.state["motion"] = "stop"
            return SkillResult(
                status="success",
                message="Le robot est arrêté.",
                data={"motion": "stop"},
                confidence=1.0,
                next_action=None,
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors de l'arrêt du robot : {exc}",
                data={"error": str(exc)},
                confidence=0.0,
                next_action=None,
            )
