from __future__ import annotations

import pytest

from irobot.interfaces import plan_guards as pg


def step(intent, target=None, **params):
    return {"intent": intent, "target": target, "parameters": params}


def P(**params):
    return {"parameters": params}


CASES = [
    # intent non justifié
    ("chante une chanson", [step("spin_360")], None, "intent 'spin_360' non justifié par la phrase", []),
    # stop parasite supprimé, le reste conservé
    ("avance de 2 metres", [step("stop"), step("move_forward", distance=2)],
     [step("move_forward", distance=2)], None, ["stop parasite supprimé"]),
    # paramètre inutile
    ("avance de 2 metres", [step("move_forward", distance=2, speed=5)],
     [step("move_forward", distance=2)], None, ["move_forward.speed inutile : supprimé"]),
    # nombre absent, phrase sans chiffre : supprimé puis défaut ajouté
    ("avance", [step("move_forward", distance=3)],
     [step("move_forward", duration=1)], None, ["move_forward.distance=3 absent de la phrase : supprimé"]),
    # nombre absent, phrase avec chiffres : rejet
    ("avance de 2 metres", [step("move_forward", distance=5)],
     None, "move_forward.distance=5 ne correspond à aucun nombre de la phrase", []),
    # duration 1 tolérée, rien à ajouter
    ("avance", [step("move_forward", duration=1)], [step("move_forward", duration=1)], None, []),
    # angle 90 toléré
    ("tourne a gauche", [step("turn_left", angle=90)], [step("turn_left", angle=90)], None, []),
    # duration 1 non tolérée pour turn_left
    ("tourne a gauche", [step("turn_left", duration=1)], [step("turn_left", angle=90)], None,
     ["turn_left.duration=1 absent de la phrase : supprimé"]),
    # durée par défaut ajoutée
    ("recule", [step("move_backward")], [step("move_backward", duration=1)], None, []),
    # angle par défaut ajouté
    ("tourne a droite", [step("turn_right")], [step("turn_right", angle=90)], None, []),
    # parameters absent : défaut ajouté
    ("avance", [{"intent": "move_forward"}], [{"intent": "move_forward", "parameters": {"duration": 1}}], None, []),
    # étape non dict
    ("avance", ["avance"], None, "étape invalide", []),
    # marqueur
    ("suis moi", [step("follow_person", target="yellow")], None,
     "moi désigne le visage : target doit être face", []),
    # refus de suivi
    ("suis le chat", [step("follow_object")], None, "unsupported_follow_target", []),
    # intent sans règle : aucun contrôle
    ("avance", [step("execute_path", foo=1)], [step("execute_path", foo=1)], None, []),
]


@pytest.mark.parametrize(("text", "steps", "kept", "reason", "notes"), CASES)
def test_grounding_check_behavior(text, steps, kept, reason, notes):
    got_kept, got_reason, got_notes = pg.grounding_check(text, steps)

    assert got_reason == reason
    assert got_kept == ([] if kept is None else kept)
    assert got_notes == notes


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"intent": "follow_object", "target": "chat"}, True),
        ({"intent": "follow_object", "parameters": "x"}, True),
        ({"intent": "follow_object", "parameters": {"target_object": "chat"}}, True),
        ({"intent": "follow_object", "target": "red"}, False),
        ({"intent": "move_forward", "target": "chat"}, False),
        ([{"steps": [{"name": "follow_person", "target": "chat"}]}], True),
        ("texte", False),
    ],
)
def test_contains_unsupported_follow_step(value, expected):
    assert pg.contains_unsupported_follow_step(value) is expected
