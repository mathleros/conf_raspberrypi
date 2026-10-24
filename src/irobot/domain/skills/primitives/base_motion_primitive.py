from __future__ import annotations

from typing import Any

from irobot.config.settings import load_runtime_settings
from irobot.domain.skills.base_skill import Skill, SkillContext, SkillResult

SETTINGS = load_runtime_settings()


class BaseMotionPrimitiveSkill(Skill):
    """Classe de base factorisée pour les primitives de mouvement."""

    motion: str = "motion"
    command_method: str = ""
    command_for_method: str = ""
    parameter_mode: str = "distance"  # distance|angle
    success_message: str = "Mouvement exécuté."
    failure_message: str = "Le robot ne fournit pas la méthode requise"
    error_prefix: str = "Erreur lors du mouvement"

    def validate(self, context: SkillContext) -> bool:
        return context.robot is not None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _resolve_motion_parameters(self, context: SkillContext) -> dict[str, Any]:
        params = dict(context.state.get("active_intent_parameters") or {})

        if self.parameter_mode == "angle":
            angle = params.get("angle")
            if angle is None and params.get("full_rotation"):
                angle = 360
            angle_value = self._to_float(angle)
            duration_value = self._to_float(params.get("duration"))
            if duration_value is None and angle_value is not None:
                duration_value = max(0.1, angle_value / SETTINGS.deg_per_second)
            return {
                "angle": angle_value,
                "duration": duration_value,
            }

        distance = params.get("distance", params.get("side"))
        unit = str(params.get("unit", "cm")) if distance is not None else None
        distance_value = self._to_float(distance)
        duration_value = self._to_float(params.get("duration"))
        if duration_value is None and distance_value is not None:
            distance_cm = distance_value * 100.0 if unit == "m" else distance_value
            duration_value = max(0.1, distance_cm / SETTINGS.cm_per_second)
        return {
            "distance": distance_value,
            "unit": unit,
            "duration": duration_value,
        }

    def _execute_motion(self, context: SkillContext, duration_value: float | None) -> bool:
        command = getattr(context.robot, self.command_method, None)
        if not callable(command):
            return False

        command_for = getattr(context.robot, self.command_for_method, None)
        if duration_value is not None and callable(command_for):
            command_for(duration_value)
        else:
            command()
        return True

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            payload = self._resolve_motion_parameters(context)
            duration_value = self._to_float(payload.get("duration"))

            if not self._execute_motion(context, duration_value):
                return SkillResult(
                    status="failed",
                    message=self.failure_message,
                    data={"skill": self.name},
                    confidence=0.0,
                    next_action=None,
                )

            context.state["motion"] = self.motion
            return SkillResult(
                status="success",
                message=self.success_message,
                data={"motion": self.motion, **payload},
                confidence=1.0,
                next_action="track_target",
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"{self.error_prefix} : {exc}",
                data={"error": str(exc), "skill": self.name},
                confidence=0.0,
                next_action=None,
            )
