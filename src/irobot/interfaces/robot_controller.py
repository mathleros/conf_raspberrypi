from __future__ import annotations

import time
from typing import Any


class RobotController:
    """Adapter between robot business logic and hardware implementation."""

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
            return bool(self.robot.check_obstacle())
        return False

    def forward_for(self, duration_seconds: float) -> None:
        if hasattr(self.robot, "forward_for"):
            self.robot.forward_for(duration_seconds)
            return
        self.forward()
        time.sleep(max(0.0, duration_seconds))
        self.stop()

    def backward_for(self, duration_seconds: float) -> None:
        if hasattr(self.robot, "backward_for"):
            self.robot.backward_for(duration_seconds)
            return
        self.backward()
        time.sleep(max(0.0, duration_seconds))
        self.stop()

    def left_for(self, duration_seconds: float) -> None:
        if hasattr(self.robot, "left_for"):
            self.robot.left_for(duration_seconds)
            return
        self.left()
        time.sleep(max(0.0, duration_seconds))
        self.stop()

    def right_for(self, duration_seconds: float) -> None:
        if hasattr(self.robot, "right_for"):
            self.robot.right_for(duration_seconds)
            return
        self.right()
        time.sleep(max(0.0, duration_seconds))
        self.stop()

    def __getattr__(self, name: str):
        return getattr(self.robot, name)
