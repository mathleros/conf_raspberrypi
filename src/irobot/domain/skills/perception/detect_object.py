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
            distance_cm = context.state.get("last_object_distance_cm")
            approach_threshold_cm = float(params.get("approach_threshold_cm", 20.0))

            if position in {None, "UNKNOWN"}:
                return SkillResult(
                    status="failed",
                    message=f"Aucun objet détecté ({target_object}).",
                    data={"position": None, "target_object": target_object},
                    confidence=0.0,
                    next_action="scan_for_target",
                )

            context.state["last_object_position"] = position
            close_enough = False
            if distance_cm is not None:
                try:
                    close_enough = float(distance_cm) <= max(1.0, approach_threshold_cm)
                except (TypeError, ValueError):
                    close_enough = False
            context.state["close_enough"] = close_enough

            return SkillResult(
                status="success",
                message=f"Objet détecté ({target_object}).",
                data={
                    "position": position,
                    "target_object": target_object,
                    "distance_cm": distance_cm,
                    "close_enough": close_enough,
                    "approach_threshold_cm": max(1.0, approach_threshold_cm),
                },
                confidence=0.8,
                next_action="stop_motion" if close_enough else "align_to_target",
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors de la détection : {exc}",
                data={"error": str(exc), "skill": self.name},
                confidence=0.0,
                next_action=None,
            )
