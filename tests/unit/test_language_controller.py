from __future__ import annotations

import pytest

from irobot.app.domain.intent_validator import IntentValidator
from irobot.app.interfaces.intent.text_intent_parser import TextIntentParser
from irobot.app.interfaces.command_service import CommandService
from irobot.app.domain.orchestrator.planner import SkillPlanner
from irobot.app.interfaces.language_controller import LanguageController
from irobot.common.interfaces.perception_contracts import ObjectDetection
from tests.unit.fake_robot import FakeRobot



def test_intent_parser_follow_red_ball():
    intent = TextIntentParser().parse("va vers la balle rouge")

    assert intent.name == "follow_red_ball"
    assert intent.target == "red_ball"
    assert intent.confidence > 0.5


def test_intent_parser_and_planner_follow_person():
    parser = TextIntentParser()
    validator = IntentValidator()
    for phrase in ("suis-moi", "suis moi", "suivez-moi"):
        intent = parser.parse(phrase)
        assert intent.name == "follow_person"
        assert intent.target == "face"
        assert intent.confidence == 1.0
        assert intent.raw_text == phrase
        assert validator.validate(intent)

    controller = LanguageController(robot=FakeRobot())
    assert [skill.name for skill in controller.planner.plan("follow_person")] == ["follow_object"]


@pytest.mark.parametrize("phrase", [
    "approche toi de moi", "approche-toi de moi", "Approche-toi de moi !",
    "rapproche-toi de moi", "rejoins-moi",
])
def test_intent_parser_approach_me_targets_face(phrase):
    intent = TextIntentParser().parse(phrase)

    assert intent.name == "search_and_approach_object"
    assert intent.target == "face"
    assert intent.raw_text == phrase
    assert IntentValidator().validate(intent)


def test_intent_parser_stop():
    intent = TextIntentParser().parse("stop maintenant")

    assert intent.name == "stop"


def test_intent_validator_accepts_known_intent():
    intent = TextIntentParser().parse("tourne à gauche pendant 2s")
    assert IntentValidator().validate(intent) is True


def test_intent_parser_recognizes_spin_square_and_return():
    spin = TextIntentParser().parse("fais un tour sur toi même")
    square = TextIntentParser().parse("forme un carré de 40 cm")
    back = TextIntentParser().parse("reviens au point de départ")

    assert spin.name == "spin_360"
    assert square.name == "move_square"
    assert square.parameters["side"] == 40
    assert back.name == "return_to_start"


def test_intent_parser_recognizes_search_and_approach_object():
    intent = TextIntentParser().parse("détecte un objet bouteille puis approche toi")

    assert intent.name == "search_and_approach_object"
    assert intent.parameters["search"] is True
    assert intent.parameters["approach"] is True


def test_language_controller_handles_text_command():
    controller = LanguageController(robot=FakeRobot())
    intent = TextIntentParser().parse("va vers la balle rouge")
    result = controller.handle_planned_step(controller.planner.plan_intents([intent])[0])

    assert result["status"] == "accepted"
    assert len(result["plan"]) > 0


def test_language_controller_handles_contour_obstacle_command():
    service = CommandService(robot=FakeRobot(), use_llm=False)
    result = service.handle_text("contourne l'objet devant toi à 20 cm")

    assert result["status"] == "accepted"
    assert result["steps"][0]["plan"][0] == "turn_right"


def test_language_controller_handles_search_and_approach_object_command():
    controller = LanguageController(robot=FakeRobot())
    intent = TextIntentParser().parse("cherche un objet puis approche toi")
    result = controller.handle_planned_step(controller.planner.plan_intents([intent])[0])

    assert result["status"] == "accepted"
    assert result["plan"][0] == "detect_object"
    assert "approach_target" in result["plan"]


def test_command_service_is_the_text_entry_point():
    service = CommandService(robot=FakeRobot(), use_llm=False)
    result = service.handle_text("avance")

    assert result["status"] == "accepted"
    assert result["source"] == "local_parser"
    assert [step["intent"].name for step in result["steps"]] == ["move_forward"]


def test_skill_planner_compiles_compound_intents_to_typed_skill_steps():
    planner = SkillPlanner()
    parsed = TextIntentParser().parse("forme un carré de 30 cm")
    expanded = planner.expand_intents([parsed])
    steps = planner.plan_intents(expanded)

    assert len(steps) == 8
    assert [step.intent.name for step in steps] == [
        "move_forward", "turn_right", "move_forward", "turn_right",
        "move_forward", "turn_right", "move_forward", "turn_right",
    ]
    assert all([skill.name for skill in step.skills] == [step.intent.name] for step in steps)


def test_language_controller_prioritizes_obstacle_stop():
    robot = FakeRobot()
    robot.obstacle_detected = True
    controller = LanguageController(robot=robot)

    intent = TextIntentParser().parse("avance")
    result = controller.handle_planned_step(controller.planner.plan_intents([intent])[0])

    assert result["status"] == "aborted"
    assert result["reason"] == "obstacle prioritized"
    assert result["results"][0].data["motion"] == "stop"


def test_language_controller_injects_perception_detection():
    class FakePerception:
        def detect(self, *, target):
            return ObjectDetection(
                label=target.value, position="center", distance_cm=15.0, confidence=0.9
            )

    controller = LanguageController(
        robot=FakeRobot(),
        perception=FakePerception(),
            )
    intent = TextIntentParser().parse("cherche la balle rouge puis approche toi")
    result = controller.handle_planned_step(controller.planner.plan_intents([intent])[0])

    assert result["status"] == "accepted"


def test_parse_plan_extracts_person_for_approach_and_follow() -> None:
    parser = TextIntentParser()

    named = parser.parse_plan("approche toi de mathieu")[0]
    assert (named.name, named.target, named.parameters) == (
        "search_and_approach_object", "face", {"person": "Mathieu"},
    )
    for text in ("approche toi de moi", "approche toi de la balle jaune"):
        assert "person" not in parser.parse_plan(text)[0].parameters
    follow = parser.parse_plan("suis mathieu")[0]
    assert (follow.name, follow.parameters) == ("follow_person", {"person": "Mathieu"})


def test_parse_plan_splits_on_et_only_before_action_verb() -> None:
    parser = TextIntentParser()

    plan = parser.parse_plan("suis mathieu et avance")
    assert [(i.name, i.parameters) for i in plan] == [
        ("follow_person", {"person": "Mathieu"}), ("move_forward", {"duration": 1.0}),
    ]
    assert [i.name for i in parser.parse_plan("avance, recule et tourne à droite")] == [
        "move_forward", "move_backward", "turn_right",
    ]


def test_parse_plan_keeps_et_inside_non_action_phrases() -> None:
    parser = TextIntentParser()

    assert [i.name for i in parser.parse_plan("tourne à gauche et à droite")] == ["turn_left"]
    duration = parser.parse_plan("avance pendant une minute et trente secondes")
    assert [(i.name, i.parameters) for i in duration] == [("move_forward", {"duration": 90.0})]
    mixed = parser.parse_plan("cherche mathieu et suis le pendant 5 minutes")
    assert [(i.name, i.parameters.get("person"), i.parameters.get("duration_s")) for i in mixed] == [
        ("search_and_approach_object", "Mathieu", None), ("follow_person", "Mathieu", 300.0),
    ]