"""Interface layer between domain logic and hardware adapters."""


def __getattr__(name):
    if name == "CommandService":
        from irobot.app.interfaces.command_service import CommandService

        return CommandService
    if name == "LanguageController":
        from irobot.app.interfaces.language_controller import LanguageController

        return LanguageController
    if name == "VoiceRuntime":
        from irobot.app.interfaces.voice_runtime import VoiceRuntime

        return VoiceRuntime
    if name == "RobotController":
        from irobot.app.interfaces.robot_controller import RobotController

        return RobotController
    raise AttributeError(name)

__all__ = [
    "CommandService",
    "LanguageController",
    "RobotController",
    "VoiceRuntime",
]
