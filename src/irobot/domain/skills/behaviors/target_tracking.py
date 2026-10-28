from __future__ import annotations

from collections.abc import Callable
from typing import Any

from irobot.domain.skills.base_skill import SkillContext


class TargetTrackingMixin:
    """Briques communes aux behaviors de suivi visuel (détection, sécurité, balayage)."""

    SEARCH_SETTLE_S = 0.15

    sleep_fn: Callable[[float], None]

    @staticmethod
    def _to_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_position(position: Any) -> str | None:
        if position is None:
            return None
        normalized = str(position).strip().lower()
        if normalized in {"center", "centre", "middle"}:
            return "center"
        if normalized in {"left", "right"}:
            return normalized
        return None

    def _check_obstacle_fail_safe(self, context: SkillContext) -> bool:
        if bool(context.state.get("obstacle_detected", False)):
            return True

        checker = getattr(context.robot, "check_obstacle", None)
        if checker is None:
            return False

        try:
            reading = checker()
        except Exception:
            return True

        if reading is None:
            return True
        return bool(reading)

    def _is_emergency_stop_requested(self, context: SkillContext) -> bool:
        robot = context.robot
        detector = getattr(robot, "_is_emergency_stop_requested", None) or getattr(
            robot, "is_emergency_stop_requested", None
        )
        if not callable(detector):
            return False
        try:
            return bool(detector())
        except Exception:
            return True

    def _stop_robot(self, context: SkillContext) -> None:
        stop = getattr(context.robot, "stop", None)
        if callable(stop):
            stop()

    def _pulse_motion(self, context: SkillContext, direction: str, duration_s: float) -> None:
        duration = max(0.0, float(duration_s))
        directional_for = getattr(context.robot, f"{direction}_for", None)
        if callable(directional_for):
            directional_for(duration)
            return

        directional = getattr(context.robot, direction, None)
        if callable(directional):
            directional()
            if duration > 0.0:
                self.sleep_fn(duration)

    def _sweep_step(
        self,
        context: SkillContext,
        direction: str,
        step_s: float,
        iterations: int,
    ) -> None:
        """Une impulsion de balayage de recherche suivie d'un temps de stabilisation."""
        self._pulse_motion(context, direction, step_s)
        context.state["motion"] = "search_target"
        context.state["follow_target_state"] = {
            "phase": "searching",
            "direction": direction,
            "iterations": iterations,
        }
        self.sleep_fn(self.SEARCH_SETTLE_S)

    def _detect_target(self, context: SkillContext) -> tuple[str | None, float | None]:
        params = dict(context.state.get("active_intent_parameters") or {})
        target_object = params.get("target_object") or context.state.get("target_object")
        detector = getattr(context.perception, "detect", None)

        if callable(detector):
            detection = detector(target=target_object)
            if detection is None:
                context.state["last_object_position"] = None
                context.state["last_object_distance_cm"] = None
                context.state["last_ball_position"] = None
            else:
                context.state["target_object"] = getattr(detection, "label", target_object) or target_object
                context.state["last_object_position"] = getattr(detection, "position", None)
                context.state["last_object_distance_cm"] = getattr(detection, "distance_cm", None)

        raw_position = context.state.get("last_object_position") or context.state.get("last_ball_position")
        position = self._normalize_position(raw_position)

        distance_raw = context.state.get("last_object_distance_cm")
        try:
            distance_cm = float(distance_raw) if distance_raw is not None else None
        except (TypeError, ValueError):
            distance_cm = None
        return position, distance_cm
