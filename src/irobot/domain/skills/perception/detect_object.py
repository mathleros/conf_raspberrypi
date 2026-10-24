from __future__ import annotations

from irobot.domain.skills.base_skill import Skill, SkillContext, SkillResult


class DetectObjectSkill(Skill):
    """Skill de perception : détecte un objet cible dans le champ visuel."""

    name = "detect_object"
    description = "Retourne la position d'un objet cible si elle est visible"

    def validate(self, context: SkillContext) -> bool:
        return context.camera is not None or context.state.get("camera_ready") is True or context.robot is not None

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            params = dict(context.state.get("active_intent_parameters") or {})
            target_object = params.get("target_object") or context.state.get("target_object") or "object"

            position = context.state.get("last_object_position")
            if position is None:
                position = context.state.get("last_ball_position", "UNKNOWN")

            if position in {None, "UNKNOWN"}:
                return SkillResult(
                    status="failed",
                    message=f"Aucun objet détecté ({target_object}).",
                    data={"position": None, "target_object": target_object},
                    confidence=0.0,
                    next_action="scan_for_target",
                )

            context.state["last_object_position"] = position

            return SkillResult(
                status="success",
                message=f"Objet détecté ({target_object}).",
                data={"position": position, "target_object": target_object},
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
