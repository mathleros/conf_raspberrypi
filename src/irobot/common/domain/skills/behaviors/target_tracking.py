from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from irobot.common.config.settings import RuntimeSettings, load_runtime_settings
from irobot.common.domain.numbers import to_float
from irobot.common.domain.skills.base_skill import SkillContext

FOLLOW_INTENTS = frozenset({"follow_person", "follow_red_ball", "follow_object"})

Direction = Literal["forward", "backward", "left", "right"]
Position = Literal["left", "right", "center"]


@dataclass
class OvershootRecovery:
    """Mémorise la dernière impulsion d'alignement ; si la cible disparaît juste après, propose l'impulsion inverse."""

    max_attempts: int
    settle_s: float
    window_s: float
    attempts_left: int = 0
    direction: Direction | None = None
    duration_s: float = 0.0
    pulsed_at: float = 0.0

    def aligned(self, direction: Direction, duration_s: float, now: float) -> None:
        self.direction, self.duration_s, self.pulsed_at = direction, duration_s, now
        self.attempts_left = self.max_attempts

    def reverse(self, now: float) -> tuple[Direction, float] | None:
        """(direction, durée) de l'impulsion inverse à jouer, ou None si aucune tentative n'est justifiée."""
        if self.direction is None or self.attempts_left <= 0 or not self.settle_s <= now - self.pulsed_at <= self.window_s:
            return None
        self.attempts_left -= 1
        self.pulsed_at = now
        return ("left" if self.direction == "right" else "right"), self.duration_s


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

    def _align_step_s(self, offset_x: float | None, fallback_s: float) -> float:
        """Durée de l'impulsion d'alignement : angle estimé du décalage / vitesse de rotation, atténué par `align_gain`."""
        settings = self.settings
        if offset_x is None:
            return fallback_s
        half_width_px = settings.camera_oriented_frame_size_px[0] / 2.0
        angle_deg = math.degrees(math.atan(abs(offset_x) * half_width_px / settings.camera_focal_px))
        step_s = settings.align_gain * angle_deg / settings.deg_per_second
        return min(max(step_s, settings.align_step_min_seconds), settings.align_step_max_seconds)

    def _needs_angular_correction(
        self, position: str | None, distance_cm: float | None, offset_x: float | None, band_max_cm: float,
    ) -> bool:
        """Rotation seulement si la cible est hors consigne (distance inconnue ou > band_max_cm) ou au bord de l'image."""
        if position not in {"left", "right"}:
            return False
        too_far = distance_cm is None or distance_cm > band_max_cm
        at_edge = offset_x is not None and abs(offset_x) >= self.settings.camera_edge_offset_threshold
        return too_far or at_edge

    def _detect_target(self, context: SkillContext) -> tuple[str | None, float | None]:
        detector = getattr(context.perception, "detect", None)

        if callable(detector) and context.perception_target is not None:
            detection = detector(target=context.perception_target)
            if detection is None:
                context.state["last_object_position"] = None
                context.state["last_object_offset_x"] = None
                context.state["last_object_cached"] = False
                context.state["last_object_distance_cm"] = None
                context.state["last_ball_position"] = None
            else:
                context.state["target_object"] = getattr(detection, "label", None)
                context.state["last_object_position"] = getattr(detection, "position", None)
                context.state["last_object_offset_x"] = getattr(detection, "offset_x", None)
                context.state["last_object_cached"] = bool(getattr(detection, "cached", False))
                context.state["last_object_distance_cm"] = getattr(detection, "distance_cm", None)

        # Une détection mémorisée ne doit pas piloter le robot : la cible est considérée non vue.
        if context.state.get("last_object_cached"):
            return None, None

        raw_position = context.state.get("last_object_position") or context.state.get("last_ball_position")
        position = self._normalize_position(raw_position)

        distance_cm = to_float(context.state.get("last_object_distance_cm"))
        return position, distance_cm
