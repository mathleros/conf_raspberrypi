from __future__ import annotations

from irobot.interfaces.intent_parser import IntentParser, IntentValidator
from irobot.interfaces.language_controller import LanguageController
from irobot.interfaces.perception_pipeline import ObjectDetection
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


def test_intent_parser_recognizes_spin_square_and_return():
    spin = IntentParser().parse("fais un tour sur toi même")
    square = IntentParser().parse("forme un carré de 40 cm")
    back = IntentParser().parse("reviens au point de départ")

    assert spin.name == "spin_360"
    assert square.name == "move_square"
    assert square.parameters["side"] == 40
    assert back.name == "return_to_start"


def test_intent_parser_recognizes_search_and_approach_object():
    intent = IntentParser().parse("détecte un objet bouteille puis approche toi")

    assert intent.name == "search_and_approach_object"
    assert intent.parameters["search"] is True
    assert intent.parameters["approach"] is True


def test_language_controller_handles_text_command():
    controller = LanguageController(robot=FakeRobot())
    result = controller.handle_text("va vers la balle rouge")

    assert result["status"] == "accepted"
    assert len(result["plan"]) > 0


def test_language_controller_handles_contour_obstacle_command():
    controller = LanguageController(robot=FakeRobot())
    result = controller.handle_text("contourne l'objet devant toi à 20 cm")

    assert result["status"] == "accepted"
    assert result["plan"][0] == "turn_right"


def test_language_controller_handles_search_and_approach_object_command():
    controller = LanguageController(robot=FakeRobot())
    result = controller.handle_text("cherche un objet puis approche toi")

    assert result["status"] == "accepted"
    assert result["plan"][0] == "detect_object"
    assert "follow_target" in result["plan"]


def test_language_controller_prioritizes_obstacle_stop():
    robot = FakeRobot()
    robot.obstacle_detected = True
    controller = LanguageController(robot=robot)

    result = controller.handle_text("avance")

    assert result["status"] == "aborted"
    assert result["reason"] == "obstacle prioritized"
    assert result["results"][0].data["motion"] == "stop"


def test_language_controller_injects_perception_detection():
    class FakePerception:
        def detect(self, *, target=None):
            return ObjectDetection(label=target or "object", position="center", distance_cm=15.0, confidence=0.9)

    controller = LanguageController(robot=FakeRobot(), perception=FakePerception())
    result = controller.handle_text("cherche un objet puis approche toi")

    assert result["status"] == "accepted"
