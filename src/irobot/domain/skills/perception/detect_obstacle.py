from __future__ import annotations

from irobot.domain.skills.base_skill import Skill, SkillContext, SkillResult


class DetectObstacleSkill(Skill):
    """Skill de perception : indique si un obstacle est trop proche."""

    name = "detect_obstacle"
    description = "Lit le capteur de distance et retourne la présence d'un obstacle"

    def validate(self, context: SkillContext) -> bool:
        return context.robot is not None

    def execute(self, context: SkillContext) -> SkillResult:
        if context.robot is None:
            return SkillResult(
                status="failed",
                message="Robot indisponible : détection d'obstacle impossible",
                data={"skill": self.name},
                confidence=0.0,
                next_action=None,
            )
        try:
            obstacle = bool(context.robot.check_obstacle())
            context.state["obstacle_detected"] = obstacle
            distance_cm = getattr(context.robot, "last_obstacle_distance_cm", None)
            context.state["obstacle_distance_cm"] = distance_cm

            if obstacle:
                return SkillResult(
                    status="success",
                    message="Obstacle détecté à proximité.",
                    data={"obstacle_detected": True, "obstacle_distance_cm": distance_cm},
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
