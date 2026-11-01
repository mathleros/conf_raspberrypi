"""Timed motion using an injected clock and an emergency cancellation signal."""

from __future__ import annotations

from collections.abc import Callable
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from irobot.interfaces.robot_controller import RobotController


def run_motion_for(
    self: RobotController, start_motion: Callable[[], None], duration_seconds: float,
    check_obstacle: bool = True,
) -> str | None:
    try:
        if (isinstance(duration_seconds, bool)
                or not isinstance(duration_seconds, (int, float))
                or not math.isfinite(duration_seconds) or duration_seconds < 0):
            raise ValueError("Motion duration must be finite and non-negative")
        if self._is_emergency_stop_requested():
            return "emergency_stop"
        if check_obstacle and self.check_obstacle():
            return "obstacle"
        if self._is_emergency_stop_requested():
            return "emergency_stop"
        start_motion()
        if duration_seconds == 0:
            return None
        deadline = self.time_fn() + duration_seconds
        while True:
            if self._is_emergency_stop_requested():
                return "emergency_stop"
            if check_obstacle and self.check_obstacle():
                return "obstacle"
            if self._is_emergency_stop_requested():
                return "emergency_stop"
            remaining = deadline - self.time_fn()
            if remaining <= 0.0:
                return None
            self.sleep_fn(min(self.CONTROL_LOOP_PERIOD_S, remaining))
    finally:
        self.stop()
