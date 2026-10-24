from __future__ import annotations

from typing import Any

from irobot.config.settings import load_runtime_settings
from irobot.domain.skills.base_skill import Skill, SkillContext, SkillResult

SETTINGS = load_runtime_settings()


class TurnRightSkill(Skill):
    """Skill primitive : tourne le robot vers la droite."""

    name = "turn_right"
    description = "Tourne le robot vers la droite à la vitesse courante"

    def validate(self, context: SkillContext) -> bool:
        return context.robot is not None

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            params = dict(context.state.get("active_intent_parameters") or {})
            angle = params.get("angle")
            if angle is None and params.get("full_rotation"):
                angle = 360
            duration = params.get("duration")

            def _to_float(value: Any) -> float | None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            angle_value = _to_float(angle)
            duration_value = _to_float(duration)
            if duration_value is None and angle_value is not None:
                duration_value = max(0.1, angle_value / SETTINGS.deg_per_second)

            if hasattr(context.robot, "right"):
                if duration_value is not None and hasattr(context.robot, "right_for"):
                    context.robot.right_for(duration_value)
                else:
                    context.robot.right()
            else:
                return SkillResult(
                    status="failed",
                    message="Le robot ne fournit pas de méthode right()",
                    data={"skill": self.name},
                    confidence=0.0,
                    next_action=None,
                )

            context.state["motion"] = "right"
            return SkillResult(
                status="success",
                message="Rotation droite exécutée.",
                data={"motion": "right", "angle": angle_value, "duration": duration_value},
                confidence=0.9,
                next_action="track_target",
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors de la rotation droite : {exc}",
                data={"error": str(exc), "skill": self.name},
                confidence=0.0,
                next_action=None,
            )
