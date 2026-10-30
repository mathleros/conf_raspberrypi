"""Interface layer between domain logic and hardware adapters."""

from irobot.interfaces.intent_parser import Intent, IntentParser, IntentValidator
from irobot.interfaces.language_controller import LanguageController
from irobot.interfaces.robot_controller import RobotController


def __getattr__(name):
    if name == "VoiceRuntime":
        from irobot.interfaces.voice_runtime import VoiceRuntime
        return VoiceRuntime
    raise AttributeError(name)

__all__ = [
    "Intent",
    "IntentParser",
    "IntentValidator",
    "LanguageController",
    "RobotController",
    "VoiceRuntime",
]
