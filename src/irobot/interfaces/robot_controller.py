from __future__ import annotations

import time
from typing import Any


class RobotController:
    """Adapter between robot business logic and hardware implementation."""

    CONTROL_LOOP_PERIOD_S = 0.02

    def __init__(self, robot: Any):
        self.robot = robot

    def forward(self) -> None:
        if hasattr(self.robot, "forward"):
            self.robot.forward()
            return
        raise AttributeError("Le robot ne fournit pas de méthode forward().")

    def backward(self) -> None:
        if hasattr(self.robot, "backward"):
            self.robot.backward()
            return
        raise AttributeError("Le robot ne fournit pas de méthode backward().")

    def left(self) -> None:
        if hasattr(self.robot, "left"):
            self.robot.left()
            return
        raise AttributeError("Le robot ne fournit pas de méthode left().")

    def right(self) -> None:
        if hasattr(self.robot, "right"):
            self.robot.right()
            return
        raise AttributeError("Le robot ne fournit pas de méthode right().")

    def stop(self) -> None:
        if hasattr(self.robot, "stop"):
            self.robot.stop()
            return
        raise AttributeError("Le robot ne fournit pas de méthode stop().")

    def set_speed(self, speed: float) -> None:
        if hasattr(self.robot, "set_speed"):
            self.robot.set_speed(speed)
            return
        raise AttributeError("Le robot ne fournit pas de méthode set_speed().")

    def check_obstacle(self) -> bool:
        if hasattr(self.robot, "check_obstacle"):
            try:
                obstacle = self.robot.check_obstacle()
            except Exception:
                return True
            if obstacle is None:
                return True
            return bool(obstacle)
        return False

    def _is_emergency_stop_requested(self) -> bool:
        detectors = (
            "is_emergency_stop_requested",
            "check_emergency_stop",
            "emergency_stop_requested",
            "stop_requested",
        )
        for name in detectors:
            if not hasattr(self.robot, name):
                continue
            detector = getattr(self.robot, name)
            try:
                value = detector() if callable(detector) else detector
            except Exception:
                return True
            if bool(value):
                return True
        return False

    def _run_motion_for(self, start_motion, duration_seconds: float) -> None:
        duration = max(0.0, float(duration_seconds))
        start_motion()

        if duration <= 0.0:
            self.stop()
            return

        deadline = time.monotonic() + duration
        while True:
            if self._is_emergency_stop_requested() or self.check_obstacle():
                self.stop()
                return

            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                break

            time.sleep(min(self.CONTROL_LOOP_PERIOD_S, remaining))

        self.stop()

    def forward_for(self, duration_seconds: float) -> None:
        self._run_motion_for(self.forward, duration_seconds)

    def backward_for(self, duration_seconds: float) -> None:
        self._run_motion_for(self.backward, duration_seconds)

    def left_for(self, duration_seconds: float) -> None:
        self._run_motion_for(self.left, duration_seconds)

    def right_for(self, duration_seconds: float) -> None:
        self._run_motion_for(self.right, duration_seconds)

    def __getattr__(self, name: str):
        return getattr(self.robot, name)
