import pytest

from irobot.common.config.settings import RuntimeSettings
from irobot.app.domain.intent import Intent
from irobot.app.domain.intent_validator import IntentValidator
from irobot.app.interfaces.intent.plan_validator import IntentPlanValidator
from irobot.app.interfaces.language_controller import LanguageController
from tests.unit.fake_robot import FakeRobot


@pytest.mark.parametrize("name", sorted(IntentValidator.ALLOWED_INTENTS))
def test_domain_accepts_known_intents_without_text(name):
    assert IntentValidator().validate(Intent(name=name))


def test_domain_rejects_unknown_intent():
    assert not IntentValidator().validate(Intent(name="draw_heart"))


@pytest.mark.parametrize(
    "name,target,expected",
    [
        ("follow_object", "red", True),
        ("follow_object", "yellow", True),
        ("follow_object", "blue", False),
        ("follow_object", "red_ball", False),
        ("follow_red_ball", "red_ball", True),
        ("follow_red_ball", "yellow", False),
    ],
)
def test_domain_checks_structured_targets(name, target, expected):
    assert IntentValidator().validate(Intent(name=name, target=target)) is expected


@pytest.mark.parametrize("target", ["red", "yellow", "red_ball", "yellow_ball", "marker", None])
def test_domain_accepts_normalized_tracking_parameter(target):
    intent = Intent(name="follow_object", parameters={"target_object": target})
    assert IntentValidator().validate(intent)


@pytest.mark.parametrize("target", ["blue", "balle jaune", [], {}, 42])
def test_domain_rejects_invalid_tracking_parameter(target):
    intent = Intent(name="follow_object", parameters={"target_object": target})
    assert not IntentValidator().validate(intent)


def test_lexical_refusal_stays_outside_domain():
    intent = Intent(name="follow_object", target="red", raw_text="suis un chat")
    assert IntentValidator().validate(intent)
    validated, errors = IntentPlanValidator(RuntimeSettings()).validate([intent])
    assert not validated
    assert errors[0]["reason"] == "intent not allowed"
    controller = LanguageController(robot=FakeRobot())
    result = controller.handle_planned_step(controller.planner.plan_intents([intent])[0])
    assert result["status"] == "rejected"
    assert result["reason"] == "unsupported_follow_target"


def test_language_alias_is_normalized_before_business_validation():
    validator = IntentPlanValidator(RuntimeSettings())
    normalized = validator.normalize([
        Intent(name="follow", target="balle jaune", parameters={"target_object": "jaune"}),
    ])
    validated, errors = validator.validate(normalized)
    assert not errors
    assert validated[0].target == "yellow"
    assert validated[0].parameters["target_object"] == "yellow"
