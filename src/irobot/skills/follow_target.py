from __future__ import annotations

"""Skill de suivi d'une cible visuelle.

Cette skill est un schéma de logique de contrôle de boucle ciblée : la robot
observe la cible détectée, ajuste son orientation et avance jusqu'à ce que la
cible soit perdue ou qu'une condition de sécurité soit déclenchée.
"""

from irobot.skills.base_skill import Skill, SkillContext, SkillResult


class FollowTargetSkill(Skill):
    """Suit une cible détectée dans le champ visuel."""

    name = "follow_target"
    description = "Suit une cible visuelle tout en prenant en compte les garde-fous"

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
                next_action="detect_red_ball",
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors du suivi de cible : {exc}",
                data={"error": str(exc), "skill": self.name},
                confidence=0.0,
                next_action=None,
            )
