from __future__ import annotations

from irobot.domain.skills.base_skill import Skill, SkillContext, SkillResult


class DetectObjectSkill(Skill):
    """Skill de perception : détecte un objet cible dans le champ visuel."""

    name = "detect_object"
    description = "Retourne la position d'un objet cible si elle est visible"

    def validate(self, context: SkillContext) -> bool:
        return context.camera is not None or context.state.get("camera_ready") is True

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            position = context.state.get("last_ball_position", "UNKNOWN")

            if position == "UNKNOWN":
                return SkillResult(
                    status="failed",
                    message="Aucun objet détecté.",
                    data={"position": None},
                    confidence=0.0,
                    next_action="scan_for_target",
                )

            return SkillResult(
                status="success",
                message="Objet détecté.",
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
