from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from irobot.interfaces import plan_guards as pg
from irobot.interfaces.text_normalizer import preprocess


def _load_eval_script():
    path = Path(__file__).resolve().parents[2] / "scripts" / "test" / "eval_prompt_plan.py"
    spec = importlib.util.spec_from_file_location("eval_prompt_plan_guards", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def step(intent, target=None, **params):
    return {"intent": intent, "target": target, "parameters": params}


@pytest.mark.parametrize("text", ["stop", "arrête toi", "halte", "pause", "Arrête-toi !", "stop stop robot"])
def test_pure_stop_phrases(text):
    assert pg.is_pure_stop(text)


@pytest.mark.parametrize(
    "text", ["", "avance puis arrête", "arrête toi et recule", "stop maintenant", "toi", "robot"]
)
def test_non_pure_stop_phrases(text):
    assert not pg.is_pure_stop(text)


@pytest.mark.parametrize(
    ("text", "steps"),
    [
        ("chante une chanson", [step("spin_360")]),
        ("ouvre la porte du garage", [step("move_forward", distance=100)]),
        ("fais un salto arrière", [step("avoid_obstacle")]),
    ],
)
def test_ungrounded_intent_rejects_plan(text, steps):
    kept, reason, _ = pg.grounding_check(preprocess(text), steps)

    assert kept == []
    assert "non justifié" in reason


def test_invented_number_without_digits_is_dropped_then_default_duration():
    kept, reason, notes = pg.grounding_check("avance", [step("move_forward", distance=1)])

    assert reason is None
    assert kept[0]["parameters"] == {"duration": 1}
    assert notes == ["move_forward.distance=1 absent de la phrase : supprimé"]


def test_wrong_number_with_digits_rejects_plan():
    kept, reason, _ = pg.grounding_check(
        preprocess("avance de cinquante centimètres"), [step("move_forward", distance=500)]
    )

    assert kept == []
    assert "500" in reason


def test_parasite_stop_is_removed():
    text = preprocess("avance de vingt centimètres puis recule de dix centimètres")
    steps = [step("move_forward", distance=20), step("stop"), step("move_backward", distance=10)]

    kept, reason, notes = pg.grounding_check(text, steps)

    assert reason is None
    assert [s["intent"] for s in kept] == ["move_forward", "move_backward"]
    assert "stop parasite supprimé" in notes


def test_unhandled_parameter_is_removed():
    kept, reason, notes = pg.grounding_check(
        "reviens au point de départ", [step("return_to_start", duration=1)]
    )

    assert reason is None
    assert kept == [step("return_to_start")]
    assert notes == ["return_to_start.duration inutile : supprimé"]


def test_turn_without_angle_gets_default_and_unit_is_kept():
    kept, reason, _ = pg.grounding_check("tourne à gauche", [step("turn_left")])
    assert reason is None
    assert kept[0]["parameters"] == {"angle": 90}

    kept, reason, _ = pg.grounding_check(
        preprocess("recule de deux mètres"), [step("move_backward", distance=200, unit="centimètres")]
    )
    assert reason is None
    assert kept[0]["parameters"] == {"distance": 200, "unit": "centimètres"}


def test_use_case_is_grounded():
    text = preprocess(
        "cherche la balle jaune approche toi à un mètre de la balle jaune puis suis la pendant cinq minutes"
    )
    steps = [
        step("search_and_approach_object", "yellow", stand_off_cm=100),
        step("follow_object", "yellow", stand_off_cm=100, duration_s=300),
    ]

    assert pg.grounding_check(text, steps) == (steps, None, [])


def test_build_formats_chain():
    formats = pg.build_formats(False, True)

    assert formats[0] == {
        "type": "json_schema",
        "json_schema": {"name": "plan", "strict": True, "schema": pg.PLAN_SCHEMA},
    }
    assert formats[1:] == [{"type": "json_object", "schema": pg.PLAN_SCHEMA}, {"type": "json_object"}, None]
    assert pg.build_formats(False, False) == [{"type": "json_object"}, None]
    assert pg.build_formats(True, True) == [None]


def test_guards_match_eval_script():
    script = _load_eval_script()
    for name in ("STOP_WORDS", "INTENT_LEXICON", "NUMERIC_KEYS", "ALLOWED_PARAMS", "PLAN_SCHEMA"):
        assert getattr(pg, name) == getattr(script, name), name
    for flags in ((False, True), (False, False), (True, False)):
        assert pg.build_formats(*flags) == script.build_formats(*flags)

    texts = [case[1] for case in script.CASES] + ["stop", "pause", "Arrête-toi !", "avance puis arrête"]
    for text in texts:
        sent = preprocess(text)
        assert pg.fold(sent) == script.fold(sent), text
        assert pg.is_pure_stop(sent) == script.is_pure_stop(sent), text

    candidates = [
        [step("spin_360")],
        [step("move_forward", distance=100)],
        [step("move_forward", distance=1), step("stop")],
        [step("turn_right", angle=90, speed=2)],
        [step("return_to_start", duration=1)],
        [step("follow_object", "yellow", stand_off_cm=100, duration_s=300)],
        [step("execute_path", steps=[])],
        ["pas un objet"],
    ]
    for text in texts:
        sent = preprocess(text)
        for steps in candidates:
            assert pg.grounding_check(sent, steps) == script.grounding_check(sent, steps), (text, steps)
