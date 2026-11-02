from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from irobot.interfaces import robot_motion


class RobotController:
    """Adapter between robot business logic and hardware implementation."""

    CONTROL_LOOP_PERIOD_S = 0.02

    def __init__(
        self,
        robot: Any,
        time_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self._robot = robot
        self.time_fn = time_fn
        self.sleep_fn = sleep_fn
        self._emergency_event = threading.Event()

    @property
    def robot(self):
        return self._robot

    @property
    def speed(self):
        return self._robot.speed

    def _start_motion(self, method: str) -> None:
        if self._emergency_event.is_set():
            self.stop()
            return
        getattr(self._robot, method)()
        # A stop may arrive while the driver is starting the motion.
        if self._emergency_event.is_set():
            self.stop()

    def forward(self) -> None:
        self._start_motion("forward")

    def backward(self) -> None:
        self._start_motion("backward")

    def left(self) -> None:
        self._start_motion("left")

    def right(self) -> None:
        self._start_motion("right")

    def stop(self) -> None:
        """Deliver zero immediately, without waiting for sensors or motion loops."""
        self._robot.stop()

    def set_speed(self, speed: float) -> None:
        if speed != 0 and self._emergency_event.is_set():
            self.stop()
            return
        self._robot.set_speed(speed)
        if self._emergency_event.is_set():
            self.stop()

    def check_obstacle(self) -> bool:
        check = getattr(self._robot, "check_obstacle", None)
        if not callable(check):
            return False
        try:
            obstacle = check()
        except Exception:
            logging.getLogger(__name__).exception("Echec du capteur d'obstacle")
            return True
        if obstacle is None:
            logging.getLogger(__name__).error("Capteur d'obstacle indisponible")
            return True
        return bool(obstacle)

    def request_emergency_stop(self) -> None:
        self._emergency_event.set()
        self.stop()

    def clear_emergency_stop(self) -> None:
        self._emergency_event.clear()

    def is_emergency_stop_requested(self) -> bool:
        return self._is_emergency_stop_requested()

    def _is_emergency_stop_requested(self) -> bool:
        if self._emergency_event.is_set():
            return True
        for name in (
            "is_emergency_stop_requested", "check_emergency_stop",
            "emergency_stop_requested", "stop_requested",
        ):
            detector = getattr(self._robot, name, None)
            if detector is None:
                continue
            try:
                value = detector() if callable(detector) else detector
            except Exception:
                logging.getLogger(__name__).exception("Echec de l'entree d'arret %s", name)
                return True
            if value:
                return True
        return False

    def _run_motion_for(
        self, start_motion: Callable[[], None], duration_seconds: float,
        check_obstacle: bool = True,
    ) -> str | None:
        return robot_motion.run_motion_for(
            self, start_motion, duration_seconds, check_obstacle,
        )

    def forward_for(self, duration_seconds: float) -> str | None:
        return self._run_motion_for(self.forward, duration_seconds)

    def backward_for(self, duration_seconds: float) -> str | None:
        return self._run_motion_for(self.backward, duration_seconds, check_obstacle=False)

    def left_for(self, duration_seconds: float) -> str | None:
        return self._run_motion_for(self.left, duration_seconds)

    def right_for(self, duration_seconds: float) -> str | None:
        return self._run_motion_for(self.right, duration_seconds)

    def __getattr__(self, name: str):
        return getattr(self._robot, name)
