"""Timed motion using an injected clock, controller gates and driver."""

from __future__ import annotations

from collections.abc import Callable
import math
from typing import TYPE_CHECKING

from irobot.interfaces.protection import MissionPermit, ProtectionFault

if TYPE_CHECKING:
    from irobot.interfaces.robot_controller import RobotController


def run_motion_for(
    self: RobotController, start_motion: Callable[[], None], duration_seconds: float,
    check_obstacle: bool = True, permit: MissionPermit | None = None,
) -> str | None:
    _validate_duration(self, duration_seconds, permit)
    duration = max(0.0, float(duration_seconds))
    try:
        deadline = self.time_fn() + duration
        if self.protection_present:
            should_run, result = _start_protected(
                self, start_motion, duration, check_obstacle, permit, deadline,
            )
            if not should_run:
                return result
        if self._is_emergency_stop_requested():
            return "emergency_stop"
        if check_obstacle and self.check_obstacle():
            return "obstacle"
        if not self.protection_present:
            start_motion()
        if duration <= 0.0:
            return
        if not self.protection_present:
            deadline = self.time_fn() + duration
        return _wait_motion(self, start_motion, duration, check_obstacle, permit, deadline)
    finally:
        self.stop()


def _validate_duration(
    self: RobotController, duration_seconds: float, permit: MissionPermit | None,
) -> None:
    if self.protection_present and (
        isinstance(duration_seconds, bool) or not isinstance(duration_seconds, (int, float))
        or not math.isfinite(duration_seconds) or duration_seconds < 0
    ):
        reservation = self._reservation
        if (reservation is not None and reservation.human
                and reservation.permit == permit and reservation.phase == "active"):
            self.suspend("invalid_motion_duration")
        else:
            self.stop()
        raise ProtectionFault("invalid_motion_duration")


def _ensure_current(self: RobotController, permit: MissionPermit | None) -> None:
    if not self.valid_result(permit):
        raise ProtectionFault("+".join(self.causes or ("obsolete_context",)))


def _start_protected(
    self: RobotController, start_motion: Callable[[], None], duration: float,
    check_obstacle: bool, permit: MissionPermit | None, deadline: float,
) -> tuple[bool, str | None]:
    if start_motion.__name__ not in {"forward", "backward", "left", "right"}:
        raise ProtectionFault("invalid_motion_entry")
    if duration == 0:
        self.supervise(permit)
        _ensure_current(self, permit)
        return False, None
    reservation = self._reservation
    if (reservation is not None and not reservation.human
            and check_obstacle and self.check_obstacle()):
        self.supervise(permit)
        _ensure_current(self, permit)
        return False, "obstacle"
    self.supervise(permit, command=start_motion.__name__, motion_duration=duration,
                   command_deadline=deadline)
    return True, None


def _wait_motion(
    self: RobotController, start_motion: Callable[[], None], duration: float,
    check_obstacle: bool, permit: MissionPermit | None, deadline: float,
) -> str | None:
    while True:
        if self.protection_present:
            if self.time_fn() >= deadline:
                self.supervise(permit)
                _ensure_current(self, permit)
                return
            self.supervise(permit, command=start_motion.__name__,
                           motion_duration=duration, emit_command=False,
                           command_deadline=deadline)
            _ensure_current(self, permit)
        if self._is_emergency_stop_requested():
            return "emergency_stop"
        if check_obstacle and self.check_obstacle():
            return "obstacle"
        remaining = deadline - self.time_fn()
        if remaining <= 0.0:
            return
        self.sleep_fn(min(self.CONTROL_LOOP_PERIOD_S, remaining))
