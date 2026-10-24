from __future__ import annotations

from irobot.interfaces.intent_parser import IntentParser, IntentValidator
from irobot.interfaces.language_controller import LanguageController
from tests.unit.fake_robot import FakeRobot


def test_intent_parser_follow_red_ball():
    intent = IntentParser().parse("va vers la balle rouge")

    assert intent.name == "follow_red_ball"
    assert intent.target == "red_ball"
    assert intent.confidence > 0.5


def test_intent_parser_stop():
    intent = IntentParser().parse("stop maintenant")

    assert intent.name == "stop"


def test_intent_validator_accepts_known_intent():
    intent = IntentParser().parse("tourne à gauche pendant 2s")
    assert IntentValidator().validate(intent) is True


def test_language_controller_handles_text_command():
    controller = LanguageController(robot=FakeRobot())
    result = controller.handle_text("va vers la balle rouge")

    assert result["status"] == "accepted"
    assert len(result["plan"]) > 0
