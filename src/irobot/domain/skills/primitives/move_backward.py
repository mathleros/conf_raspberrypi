from __future__ import annotations

from typing import Any

from irobot.config.settings import load_runtime_settings
from irobot.domain.skills.base_skill import Skill, SkillContext, SkillResult

SETTINGS = load_runtime_settings()


class MoveBackwardSkill(Skill):
    """Skill primitive : recule le robot en ligne droite."""

    name = "move_backward"
    description = "Recule le robot en ligne droite à la vitesse courante"

    def validate(self, context: SkillContext) -> bool:
        return context.robot is not None

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            params = dict(context.state.get("active_intent_parameters") or {})
            distance = params.get("distance", params.get("side"))
            unit = str(params.get("unit", "cm")) if distance is not None else None
            duration = params.get("duration")

            def _to_float(value: Any) -> float | None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            distance_value = _to_float(distance)
            duration_value = _to_float(duration)
            if duration_value is None and distance_value is not None:
                distance_cm = distance_value * 100.0 if unit == "m" else distance_value
                duration_value = max(0.1, distance_cm / SETTINGS.cm_per_second)

            if hasattr(context.robot, "backward"):
                if duration_value is not None and hasattr(context.robot, "backward_for"):
                    context.robot.backward_for(duration_value)
                else:
                    context.robot.backward()
            else:
                return SkillResult(
                    status="failed",
                    message="Le robot ne fournit pas de méthode backward()",
                    data={"skill": self.name},
                    confidence=0.0,
                    next_action=None,
                )

            context.state["motion"] = "backward"
            return SkillResult(
                status="success",
                message="Le robot recule.",
                data={
                    "motion": "backward",
                    "distance": distance_value,
                    "unit": unit,
                    "duration": duration_value,
                },
                confidence=1.0,
                next_action="track_target",
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors du recul : {exc}",
                data={"error": str(exc), "skill": self.name},
                confidence=0.0,
                next_action=None,
            )
