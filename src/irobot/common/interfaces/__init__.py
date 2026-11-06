"""Interface layer between domain logic and hardware adapters."""


def __getattr__(name):
    if name == "RobotController":
        from irobot.common.interfaces.robot_controller import RobotController

        return RobotController
    raise AttributeError(name)


__all__ = [
    "RobotController",
]
