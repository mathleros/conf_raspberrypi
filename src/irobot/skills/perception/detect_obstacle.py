from __future__ import annotations

from irobot.skills.base_skill import Skill, SkillContext, SkillResult


class DetectObstacleSkill(Skill):
    """Skill de perception : indique si un obstacle est trop proche."""

    name = "detect_obstacle"
    description = "Lit le capteur de distance et retourne la présence d'un obstacle"

    def validate(self, context: SkillContext) -> bool:
        return context.robot is not None

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            check_obstacle = getattr(context.robot, "check_obstacle", None)
            if check_obstacle is None:
                return SkillResult(
                    status="failed",
                    message="Le robot ne fournit pas de méthode check_obstacle()",
                    data={"skill": self.name},
                    confidence=0.0,
                    next_action=None,
                )

            obstacle = bool(check_obstacle())
            context.state["obstacle_detected"] = obstacle

            if obstacle:
                return SkillResult(
                    status="success",
                    message="Obstacle détecté à proximité.",
                    data={"obstacle_detected": True},
                    confidence=0.95,
                    next_action="stop_motion",
                )

            return SkillResult(
                status="success",
                message="Aucun obstacle détecté.",
                data={"obstacle_detected": False},
                confidence=0.9,
                next_action="track_target",
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors de la détection d'obstacle : {exc}",
                data={"error": str(exc), "skill": self.name},
                confidence=0.0,
                next_action=None,
            )
