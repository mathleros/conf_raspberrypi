from __future__ import annotations

from irobot.domain.skills.base_skill import Skill, SkillContext, SkillResult


class DetectRedBallSkill(Skill):
    """Skill de perception : détecte une balle rouge dans le champ visuel."""

    name = "detect_red_ball"
    description = "Retourne la position d'une balle rouge si elle est visible"

    def validate(self, context: SkillContext) -> bool:
        return context.camera is not None or context.state.get("camera_ready") is True

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            position = context.state.get("last_ball_position", "UNKNOWN")

            if position == "UNKNOWN":
                return SkillResult(
                    status="failed",
                    message="Aucune balle rouge détectée.",
                    data={"position": None},
                    confidence=0.0,
                    next_action="scan_for_target",
                )

            return SkillResult(
                status="success",
                message="Balle rouge détectée.",
                data={"position": position},
                confidence=0.8,
                next_action="align_to_target",
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors de la détection : {exc}",
                data={"error": str(exc), "skill": self.name},
                confidence=0.0,
                next_action=None,
            )
