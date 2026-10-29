"""Robot factice utilisé pour les tests unitaires des skills.

Le but est de simuler un robot sans dépendre des GPIO ou du matériel réel.
"""

from __future__ import annotations

from collections.abc import Callable


class FakeRobot:
    """Implémentation minimale d'un robot pour les tests unitaires.

    `time_fn` (optionnel) horodate chaque commande dans `timed_commands` (horloge simulée).
    """

    def __init__(self, time_fn: Callable[[], float] | None = None):
        self.commands: list[str] = []
        self.timed_commands: list[tuple[float, str]] = []
        self.time_fn = time_fn
        self.speed = 0.5
        self.obstacle_detected = False
        self.ultrasound_cm: float | None = None

    def _record(self, command: str) -> None:
        self.commands.append(command)
        if self.time_fn is not None:
            self.timed_commands.append((self.time_fn(), command))

    def forward(self) -> None:
        self._record("forward")

    def backward(self) -> None:
        self._record("backward")

    def left(self) -> None:
        self._record("left")

    def right(self) -> None:
        self._record("right")

    def stop(self) -> None:
        self._record("stop")

    def set_speed(self, speed: float) -> None:
        self.speed = speed

    def check_obstacle(self) -> bool:
        return self.obstacle_detected

    def read_distance_cm(self) -> float | None:
        return self.ultrasound_cm
