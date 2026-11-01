"""Mission-scoped capability without driver access or delegation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from irobot.interfaces.protection import MissionPermit

if TYPE_CHECKING:
    from irobot.interfaces.robot_controller import RobotController


class MissionRobot:
    """Narrow capability: no delegation and no exposed driver."""

    __slots__ = ("__controller", "__permit")

    def __init__(self, controller: RobotController, permit: MissionPermit):
        self.__controller = controller
        self.__permit = permit

    @property
    def speed(self):
        return self.__controller.speed

    def forward(self):
        self.__controller.supervise(self.__permit, "forward")

    def backward(self):
        self.__controller.supervise(self.__permit, "backward")

    def left(self):
        self.__controller.supervise(self.__permit, "left")

    def right(self):
        self.__controller.supervise(self.__permit, "right")

    def stop(self):
        self.__controller.stop()

    def set_speed(self, value: float):
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0:
            self.stop()
        else:
            self.__controller.supervise(self.__permit, "set_speed", value)

    def check_obstacle(self):
        return self.__controller.check_obstacle()

    def read_distance_cm(self):
        return self.__controller.read_distance_cm()

    def is_emergency_stop_requested(self):
        return (self.__controller.is_emergency_stop_requested()
                or not self.__controller.valid_result(self.__permit))

    def is_protected_result_current(self):
        self.__controller.supervise()
        return self.__controller.valid_result(self.__permit)

    def _for(self, direction: str, duration: float):
        controller = self.__controller
        start = getattr(self, direction)
        return controller._run_motion_for(
            start, duration, check_obstacle=direction != "backward", permit=self.__permit,
        )

    def forward_for(self, duration):
        return self._for("forward", duration)

    def backward_for(self, duration):
        return self._for("backward", duration)

    def left_for(self, duration):
        return self._for("left", duration)

    def right_for(self, duration):
        return self._for("right", duration)

