from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from irobot.common.config.settings import RuntimeSettings, load_runtime_settings
from irobot.common.domain.numbers import to_float
from irobot.common.domain.skills.base_skill import SkillContext

FOLLOW_INTENTS = frozenset({"follow_person", "follow_red_ball", "follow_object"})

Direction = Literal["forward", "backward", "left", "right"]
Position = Literal["left", "right", "center"]


class TargetTrackingMixin:
    """Briques communes aux behaviors de suivi visuel (détection, sécurité, balayage)."""

    SEARCH_SETTLE_S = 0.15
    CONTROL_LOOP_PERIOD_S = 0.02

    sleep_fn: Callable[[float], None]
    _settings: RuntimeSettings | None

    @property
    def settings(self) -> RuntimeSettings:
        if self._settings is None:
            self._settings = load_runtime_settings()
        return self._settings

    @staticmethod
    def _normalize_position(position: Any) -> Position | None:
        if position is None:
            return None
        normalized = str(position).strip().lower()
        if normalized in {"center", "centre", "middle"}:
            return "center"
        if normalized == "left":
            return "left"
        if normalized == "right":
            return "right"
        return None

    def _check_obstacle_fail_safe(self, context: SkillContext) -> bool:
        if bool(context.state.get("obstacle_detected", False)):
            return True

        if context.robot is None:
            return False

        try:
            reading = context.robot.check_obstacle()
        except Exception:
            return True

        context.state["obstacle_distance_cm"] = getattr(context.robot, "last_obstacle_distance_cm", None)
        if reading is None:
            return True
        return bool(reading)

    def _is_emergency_stop_requested(self, context: SkillContext) -> bool:
        detector = getattr(context.robot, "emergency_stop_requested", None)
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

    def _pulse_motion(self, context: SkillContext, direction: Direction, duration_s: float) -> None:
        """Utilise `<direction>_for(duration)` si le robot l'expose ; sinon appelle `<direction>()` puis `sleep_fn(duration)`."""
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
        direction: Direction,
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
        detector = getattr(context.perception, "detect", None)

        if callable(detector) and context.perception_target is not None:
            detection = detector(target=context.perception_target)
            if detection is None:
                context.state["last_object_position"] = None
                context.state["last_object_offset_x"] = None
                context.state["last_object_distance_cm"] = None
                context.state["last_ball_position"] = None
            else:
                context.state["target_object"] = getattr(detection, "label", None)
                context.state["last_object_position"] = getattr(detection, "position", None)
                context.state["last_object_offset_x"] = getattr(detection, "offset_x", None)
                context.state["last_object_distance_cm"] = getattr(detection, "distance_cm", None)

        raw_position = context.state.get("last_object_position") or context.state.get("last_ball_position")
        position = self._normalize_position(raw_position)

        distance_cm = to_float(context.state.get("last_object_distance_cm"))
        return position, distance_cm
