from __future__ import annotations

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

    def __getattr__(self, name: str):
        return getattr(self.robot, name)
