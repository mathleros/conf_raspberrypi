"""Interface layer between domain logic and hardware adapters."""


def __getattr__(name):
    if name == "CommandService":
        from irobot.interfaces.command_service import CommandService

        return CommandService
    if name == "LanguageController":
        from irobot.interfaces.language_controller import LanguageController

        return LanguageController
    if name == "RobotController":
        from irobot.interfaces.robot_controller import RobotController

        return RobotController
    if name == "VoiceRuntime":
        from irobot.interfaces.voice_runtime import VoiceRuntime

        return VoiceRuntime
    raise AttributeError(name)

__all__ = [
    "CommandService",
    "LanguageController",
    "RobotController",
    "VoiceRuntime",
]
