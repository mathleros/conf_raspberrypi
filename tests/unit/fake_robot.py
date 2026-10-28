"""Robot factice utilisé pour les tests unitaires des skills.

Le but est de simuler un robot sans dépendre des GPIO ou du matériel réel.
"""

from __future__ import annotations


class FakeRobot:
    """Implémentation minimale d'un robot pour les tests unitaires."""

    def __init__(self):
        self.commands: list[str] = []
        self.speed = 0.5
        self.obstacle_detected = False
        self.ultrasound_cm: float | None = None

    def forward(self) -> None:
        self.commands.append("forward")

    def backward(self) -> None:
        self.commands.append("backward")

    def left(self) -> None:
        self.commands.append("left")

    def right(self) -> None:
        self.commands.append("right")

    def stop(self) -> None:
        self.commands.append("stop")

    def set_speed(self, speed: float) -> None:
        self.speed = speed

    def check_obstacle(self) -> bool:
        return self.obstacle_detected

    def read_distance_cm(self) -> float | None:
        return self.ultrasound_cm
