from __future__ import annotations

from irobot.domain.skills.base_skill import Skill, SkillContext, SkillResult


class FollowTargetSkill(Skill):
    """Behavior composite : suit une cible détectée.

    Ce behavior est un exemple de logique de niveau supérieur : il combine
    perception et primitives de déplacement.
    """

    name = "follow_target"
    description = "Suit une cible visuelle et applique des garde-fous"

    def validate(self, context: SkillContext) -> bool:
        return context.robot is not None

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            target_position = context.state.get("last_ball_position")
            obstacle_detected = bool(context.state.get("obstacle_detected", False))

            if obstacle_detected:
                return SkillResult(
                    status="success",
                    message="Arrêt de sécurité : obstacle trop proche.",
                    data={"target_position": target_position, "obstacle_detected": True},
                    confidence=0.99,
                    next_action="stop_motion",
                )

            if target_position in {None, "UNKNOWN"}:
                return SkillResult(
                    status="failed",
                    message="Cible perdue : aucun objet détecté.",
                    data={"target_position": None, "obstacle_detected": False},
                    confidence=0.0,
                    next_action="stop_motion",
                )

            if hasattr(context.robot, "forward"):
                context.robot.forward()
            else:
                return SkillResult(
                    status="failed",
                    message="Le robot ne fournit pas de méthode forward() pour suivre la cible.",
                    data={"skill": self.name},
                    confidence=0.0,
                    next_action=None,
                )

            context.state["motion"] = "follow_target"
            return SkillResult(
                status="success",
                message=f"Suivi de la cible en cours ({target_position}).",
                data={"target_position": target_position, "obstacle_detected": False},
                confidence=0.85,
                next_action="detect_object",
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors du suivi de cible : {exc}",
                data={"error": str(exc), "skill": self.name},
                confidence=0.0,
                next_action=None,
            )
