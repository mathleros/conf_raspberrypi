"""Gardes déterministes autour du LLM planificateur : le LLM propose, le lexique dispose.

Porté depuis `scripts/test/eval_prompt_plan.py` (comportement identique, vérifié par un test) :
- `is_pure_stop` : phrase d'arrêt pure traitée localement, sans LLM ;
- `grounding_check` : chaque intent et chaque nombre du plan doivent être justifiés par la phrase ;
- `PLAN_SCHEMA` / `build_formats` : sortie contrainte par schéma JSON, avec replis.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

STOP_WORDS = {"stop", "arrete", "arrete-toi", "halte", "pause", "robot", "toi", "vite",
              "s", "il", "te", "plait", "attends", "attend"}

# intent -> (préfixes de mots, mots exacts, expressions)
INTENT_LEXICON = {
    "move_forward": (("avanc", "march", "devant"), {"va", "vas", "allez", "go"}, ("tout droit", "en avant")),
    "move_backward": (("recul", "arriere", "back", "revers"), set(), ("en arriere",)),
    "turn_left": (("gauch", "left"), set(), ()),
    "turn_right": (("droite", "right"), set(), ()),
    "spin_360": (("tour", "pivot", "rotat", "360", "spin"), set(), ()),
    "follow_object": (("suis", "suit", "suiv", "poursui", "follow", "track"), set(), ()),
    "follow_red_ball": (("suis", "suit", "suiv", "poursui", "follow", "track"), set(), ()),
    "search_and_approach_object": (("cherch", "trouv", "approch", "rejoin", "search", "find",
                                    "repere", "localis"), set(), ()),
    "stop": (("stop", "arret", "halte", "pause", "attend"), set(), ()),
    "return_to_start": (("retour", "revien", "reven", "depart", "origine", "return"), set(), ()),
    "move_square": (("carre", "square"), set(), ()),
    "avoid_obstacle": (("evit", "obstacle", "contourn", "avoid"), set(), ()),
    "contour_obstacle": (("evit", "obstacle", "contourn", "avoid"), set(), ()),
}
NUMERIC_KEYS = ("distance", "duration", "angle", "stand_off_cm", "duration_s", "side")
# paramètres que chaque intent peut réellement recevoir ; tout le reste est du bruit du LLM
ALLOWED_PARAMS = {
    "move_forward": {"distance", "duration", "unit"}, "move_backward": {"distance", "duration", "unit"},
    "turn_left": {"angle", "duration", "unit"}, "turn_right": {"angle", "duration", "unit"},
    "search_and_approach_object": {"stand_off_cm", "target_object"},
    "follow_object": {"stand_off_cm", "duration_s", "target_object"},
    "move_square": {"side", "unit"},
}

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "intent": {"type": "string", "enum": [
                        "move_forward", "move_backward", "turn_left", "turn_right", "stop",
                        "search_and_approach_object", "follow_object", "follow_red_ball",
                        "avoid_obstacle", "spin_360", "move_square", "return_to_start"]},
                    "target": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "distance": {"type": "number"}, "duration": {"type": "number"},
                            "angle": {"type": "number"}, "stand_off_cm": {"type": "number"},
                            "duration_s": {"type": "number"}, "side": {"type": "number"},
                        },
                        "additionalProperties": False,
                    },
                },
                "required": ["intent"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["steps"],
    "additionalProperties": False,
}


def build_formats(no_response_format: bool, use_schema: bool) -> list[dict[str, Any] | None]:
    """`response_format` à essayer dans l'ordre (None = sans contrainte) ; suivant sur HTTP 400."""
    if no_response_format:
        return [None]
    if use_schema:
        return [
            {"type": "json_schema", "json_schema": {"name": "plan", "strict": True, "schema": PLAN_SCHEMA}},
            {"type": "json_object", "schema": PLAN_SCHEMA},
            {"type": "json_object"},
            None,
        ]
    return [{"type": "json_object"}, None]


def fold(text: str) -> str:
    """Minuscules, sans accents ni ponctuation (comparaison lexicale)."""
    t = unicodedata.normalize("NFD", (text or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", t)


def is_pure_stop(text: str) -> bool:
    """Phrase composée uniquement de mots d'arrêt : traitée localement, sans LLM."""
    words = fold(text).split()
    return bool(words) and any(w.startswith(("stop", "arret", "halte", "pause", "attend")) for w in words) \
        and all(w in STOP_WORDS or w.startswith(("arret", "attend")) for w in words)


def requests_human_follow(text: str) -> bool:
    """Refusal guard only, not a human-follow language implementation."""
    normalized = fold(text)
    return bool(re.search(
        r"\b(?:suis|suit|suivre|suivez|suivez moi|follow|track|poursuis|rejoins)\s+"
        r"(?:(?:un|une|le|la|l|cet|cette|cette personne)\s+)?"
        r"(?:moi|nous|me|us|personne|humain|humaine|homme|femme|person|human|"
        r"porteur|utilisateur|operateur|proprietaire|quelqu un)\b",
        normalized,
    )) or bool(re.search(r"\b(?:reprends|reprendre|reprenez)\s+(?:le\s+)?suivi\b", normalized))


def contains_human_step(value: Any) -> bool:
    """Refuse human payloads before malformed-step filtering or expansion."""
    if isinstance(value, dict):
        names = {str(value.get(key, "")).strip().lower() for key in ("intent", "name", "action")}
        if names & {"follow_person", "follow_human", "track_person", "resume_follow_person"}:
            return True
        return any(contains_human_step(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_human_step(item) for item in value)
    if isinstance(value, str):
        return requests_human_follow(value)
    return False


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _licensed(intent: str, folded: str) -> bool:
    rule = INTENT_LEXICON.get(intent)
    if rule is None:          # intent sans règle (execute_path...) : pas de contrôle
        return True
    prefixes, words, phrases = rule
    tokens = folded.split()
    padded = f" {' '.join(tokens)} "
    return (any(t.startswith(p) for t in tokens for p in prefixes)
            or any(t in words for t in tokens)
            or any(f" {ph} " in padded for ph in phrases))


def grounding_check(sent_text: str, steps: list) -> tuple[list, str | None, list[str]]:
    """Retourne (étapes_conservées, raison_de_rejet | None, notes).

    - intent non justifié par un mot de la phrase  -> plan REJETÉ en entier ;
    - paramètre que l'intent ne gère pas          -> supprimé (bruit du LLM) ;
    - `stop` non justifié                         -> étape supprimée (action sûre, mais parasite) ;
    - valeur numérique absente de la phrase :
        * la phrase ne contient AUCUN chiffre -> paramètre inventé, supprimé (défaut du runtime) ;
        * la phrase contient des chiffres     -> le LLM les a mal repris : plan REJETÉ ;
      (valeurs par défaut du prompt tolérées : duration 1 pour avance/recule, angle 90 pour tourne) ;
    - après nettoyage, avance/recule sans distance ni durée -> duration 1 ; tourne sans angle ni durée -> angle 90.
    """
    if requests_human_follow(sent_text) or any(
        isinstance(step, dict) and (step.get("intent") or step.get("name")) in {
            "follow_person", "resume_follow_person",
        } for step in steps
    ):
        return [], "human_capability_unavailable", []
    folded = fold(sent_text)
    numbers = {float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", folded)}
    kept, notes = [], []
    for step in steps:
        if not isinstance(step, dict):
            return [], "étape invalide", notes
        intent = step.get("intent") or step.get("name")
        if not _licensed(intent, folded):
            if intent == "stop":
                notes.append("stop parasite supprimé")
                continue
            return [], f"intent {intent!r} non justifié par la phrase", notes
        params = step.get("parameters")
        if isinstance(params, dict):
            cleaned = {}
            allowed = ALLOWED_PARAMS.get(intent, set())
            for key, value in params.items():
                if intent in INTENT_LEXICON and key not in allowed:
                    notes.append(f"{intent}.{key} inutile : supprimé")
                    continue
                num = _num(value) if key in NUMERIC_KEYS else None
                if key in NUMERIC_KEYS and num is not None and num not in numbers:
                    default = ((key == "duration" and intent in {"move_forward", "move_backward"} and num == 1)
                               or (key == "angle" and intent in {"turn_left", "turn_right"} and num == 90))
                    if not default:
                        if numbers:
                            return [], f"{intent}.{key}={value} ne correspond à aucun nombre de la phrase", notes
                        notes.append(f"{intent}.{key}={value} absent de la phrase : supprimé")
                        continue
                cleaned[key] = value
            step = {**step, "parameters": cleaned}
        if intent in {"move_forward", "move_backward"}:
            p = dict(step.get("parameters") or {})
            if not any(k in p for k in ("distance", "duration")):
                p["duration"] = 1
                step = {**step, "parameters": p}
        elif intent in {"turn_left", "turn_right"}:
            p = dict(step.get("parameters") or {})
            if not any(k in p for k in ("angle", "duration")):
                p["angle"] = 90
                step = {**step, "parameters": p}
        kept.append(step)
    return kept, None, notes
