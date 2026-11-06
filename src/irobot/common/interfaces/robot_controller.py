from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Callable
from typing import Any, Literal, Protocol

LOGGER = logging.getLogger(__name__)

Direction = Literal["forward", "backward", "left", "right"]


def _validate_duration(duration_seconds: float) -> None:
    is_number = (
        isinstance(duration_seconds, (int, float))
        and not isinstance(duration_seconds, bool)
    )
    if not is_number or not math.isfinite(duration_seconds) or duration_seconds < 0:
        raise ValueError("Motion duration must be finite and non-negative")


class DistanceSensor(Protocol):
    def read_distance_cm(self) -> float | None: ...


class RobotController:
    """Adapter between robot business logic and hardware implementation."""

    CONTROL_LOOP_PERIOD_S = 0.02
    SENSOR_READ_ATTEMPTS = 5
    SENSOR_RETRY_DELAY_S = 0.03

    def __init__(
        self,
        robot: Any,
        time_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
        *,
        distance_sensor: DistanceSensor | None = None,
        obstacle_threshold_cm: float = 5.0,
        require_obstacle_sensor: bool = False,
    ):
        self._robot = robot
        self.time_fn = time_fn
        self.sleep_fn = sleep_fn
        self._distance_sensor = distance_sensor
        self._obstacle_threshold_cm = obstacle_threshold_cm
        self._require_obstacle_sensor = bool(require_obstacle_sensor)
        self.last_obstacle_distance_cm: float | None = None
        self._emergency_event = threading.Event()

    @property
    def robot(self):
        return self._robot

    def _stop_if_emergency(self) -> bool:
        if not self._emergency_event.is_set():
            return False
        self.stop()
        return True

    def _start_motion(self, method: Direction) -> None:
        if self._stop_if_emergency():
            return
        LOGGER.info("Mouvement : %s", method)
        getattr(self._robot, method)()
        # A stop may arrive while the driver is starting the motion.
        self._stop_if_emergency()

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
        if speed != 0 and self._stop_if_emergency():
            return
        self._robot.set_speed(speed)
        self._stop_if_emergency()

    def check_obstacle(self) -> bool:
        if self._distance_sensor is not None:
            return self._check_distance_sensor(self._distance_sensor)
        if self._require_obstacle_sensor:
            return True

        check = getattr(self._robot, "check_obstacle", None)
        if not callable(check):
            return False
        try:
            obstacle = check()
        except Exception:
            LOGGER.exception("Echec du capteur d'obstacle")
            return True
        if obstacle is None:
            LOGGER.error("Capteur d'obstacle indisponible")
            return True
        return bool(obstacle)

    def _check_distance_sensor(self, sensor: DistanceSensor) -> bool:
        for attempt in range(self.SENSOR_READ_ATTEMPTS):
            try:
                distance_cm = sensor.read_distance_cm()
            except Exception:
                LOGGER.exception("Echec du capteur d'obstacle")
                return True
            if distance_cm is not None:
                self.last_obstacle_distance_cm = distance_cm
                return distance_cm < self._obstacle_threshold_cm
            if attempt < self.SENSOR_READ_ATTEMPTS - 1:
                self.sleep_fn(self.SENSOR_RETRY_DELAY_S)
        LOGGER.error("Capteur d'obstacle indisponible")
        return True

    def request_emergency_stop(self) -> None:
        self._emergency_event.set()
        self.stop()

    def clear_emergency_stop(self) -> None:
        self._emergency_event.clear()

    def emergency_stop_requested(self) -> bool:
        if self._emergency_event.is_set():
            return True
        for name in ("emergency_stop_requested", "stop_requested"):
            detector = getattr(self._robot, name, None)
            if detector is None:
                continue
            try:
                value = detector() if callable(detector) else detector
            except Exception:
                LOGGER.exception("Echec de l'entree d'arret %s", name)
                return True
            if value:
                return True
        return False

    def _abort_reason(self, check_obstacle: bool) -> str | None:
        if self.emergency_stop_requested():
            return "emergency_stop"
        if check_obstacle and self.check_obstacle():
            return "obstacle"
        if self.emergency_stop_requested():
            return "emergency_stop"
        return None

    def _run_motion_for(
        self, direction: Direction, duration_seconds: float,
        check_obstacle: bool = True,
    ) -> str | None:
        try:
            _validate_duration(duration_seconds)
            reason = self._abort_reason(check_obstacle)
            if reason:
                return reason
            self._start_motion(direction)
            if duration_seconds == 0:
                return None
            deadline = self.time_fn() + duration_seconds
            while True:
                reason = self._abort_reason(check_obstacle)
                if reason:
                    return reason
                remaining = deadline - self.time_fn()
                if remaining <= 0.0:
                    return None
                self.sleep_fn(min(self.CONTROL_LOOP_PERIOD_S, remaining))
        finally:
            self.stop()

    def forward_for(self, duration_seconds: float) -> str | None:
        return self._run_motion_for("forward", duration_seconds)

    def backward_for(self, duration_seconds: float) -> str | None:
        return self._run_motion_for("backward", duration_seconds, check_obstacle=False)

    def left_for(self, duration_seconds: float) -> str | None:
        return self._run_motion_for("left", duration_seconds)

    def right_for(self, duration_seconds: float) -> str | None:
        return self._run_motion_for("right", duration_seconds)

    def __getattr__(self, name: str):
        return getattr(self._robot, name)
