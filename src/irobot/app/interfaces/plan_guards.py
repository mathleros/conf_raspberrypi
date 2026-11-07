"""Gardes déterministes autour du LLM planificateur : le LLM propose, le lexique dispose.

Porté depuis `scripts/scenarios/eval_prompt_plan.py` (comportement identique, vérifié par un test) :
- `is_pure_stop` : phrase d'arrêt pure traitée localement, sans LLM ;
- `grounding_check` : chaque intent et chaque nombre du plan doivent être justifiés par la phrase ;
- `PLAN_SCHEMA` / `build_formats` : sortie contrainte par schéma JSON, avec replis.
"""

from __future__ import annotations

import re
from typing import Any

from irobot.common.interfaces.text_normalizer import fold, fr_numbers_to_digits

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
    "follow_person": (("suis", "suiv", "follow", "track"), set(), ()),
    "search_and_approach_object": (("cherch", "trouv", "approch", "rapproch", "rejoin", "search", "find",
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
    "search_and_approach_object": {"stand_off_cm", "target_object", "person"},
    "follow_object": {"stand_off_cm", "duration_s", "target_object"},
    "follow_person": {"person"},
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
                        "search_and_approach_object", "follow_object", "follow_red_ball", "follow_person",
                        "avoid_obstacle", "spin_360", "move_square", "return_to_start"]},
                    "target": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "distance": {"type": "number"}, "duration": {"type": "number"},
                            "angle": {"type": "number"}, "stand_off_cm": {"type": "number"},
                            "duration_s": {"type": "number"}, "side": {"type": "number"},
                            "person": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "required": ["intent"],
                "additionalProperties": False,
            },
        },
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


def is_pure_stop(text: str) -> bool:
    """Phrase composée uniquement de mots d'arrêt : traitée localement, sans LLM."""
    words = fold(text).split()
    return bool(words) and any(w.startswith(("stop", "arret", "halte", "pause", "attend")) for w in words) \
        and all(w in STOP_WORDS or w.startswith(("arret", "attend")) for w in words)


NON_NAME_WORDS = frozenset({
    "la", "le", "les", "l", "un", "une", "des", "the", "a", "an", "it", "them",
    "moi", "me", "nous", "us", "personne", "humain", "humaine", "homme", "femme", "person", "human",
    "balle", "balles", "ball", "balls", "objet", "objets", "object", "objects",
    "jaune", "rouge", "yellow", "red", "marqueur", "tag", "aruco",
    "pendant", "pour", "durant", "for", "during", "at", "de", "du", "d", "of", "jusqu", "until",
    "quand", "when", "puis", "ensuite", "then", "et", "and", "please", "svp", "s",
})
_NAMED_FOLLOW = re.compile(r"\b(?:suis|suit|suivre|suivez|follow|track|poursuis)\s+([a-z]+)\b")


def named_follow_target(text: str) -> str | None:
    """Prénom juste après un verbe de suivi (casse libre : Vosk transcrit en minuscules)."""
    match = _NAMED_FOLLOW.search(fold(text))
    return match.group(1).capitalize() if match and match.group(1) not in NON_NAME_WORDS else None


def requests_human_follow(text: str) -> bool:
    """Identifies human-follow wording so target validation does not reject it."""
    if named_follow_target(text):
        return True
    normalized = fold(text)
    return bool(re.search(
        r"\b(?:suis|suit|suivre|suivez|suivez moi|follow|track|poursuis|rejoins)\s+"
        r"(?:(?!(?:balles?|balls?|objets?|objects?)\b)[a-z0-9]+\s+)*"
        r"(?:moi|nous|me|us|personne|humain|humaine|homme|femme|person|human|"
        r"porteur|utilisateur|operateur|proprietaire|quelqu un|mari|ami|amie|enfant|"
        r"wife|husband|child|children|friend)s?\b",
        normalized,
    )) or bool(re.search(r"\b(?:reprends|reprendre|reprenez)\s+(?:le\s+)?suivi\b", normalized))


TARGET_COLOR_SYNONYMS = {
    "jaune": "yellow", "yellow": "yellow", "balle jaune": "yellow", "yellow_ball": "yellow",
    "rouge": "red", "red": "red", "balle rouge": "red", "red_ball": "red",
    "balle": "ball", "balles": "ball",
    "marker": "marker", "tag": "marker",
    "moi": "face", "me": "face", "humain": "face", "humaine": "face", "personne": "face",
    "visage": "face", "face": "face", "human": "face", "person": "face",
}

FOLLOW_INTENTS = {
    "follow_object", "follow_red_ball", "follow", "track", "track_object",
    "follow_target", "follow_person", "suivre", "suit",
}


def supported_follow_target(value: Any) -> bool:
    return value is None or (
        isinstance(value, str) and value.strip().lower() in TARGET_COLOR_SYNONYMS
    )


def follow_request_refusal(text: str) -> str | None:
    split_words = r"\b(?:puis|ensuite|then|and|et)\b"
    raw_segments = re.split(split_words, text or "", flags=re.IGNORECASE)
    for raw_segment, segment in zip(raw_segments, re.split(split_words, fold(text))):
        if requests_human_follow(raw_segment):
            continue
        follow = re.search(r"\b(?:suis|suit|suivre|suivez|follow|track|poursuis|rejoins)\b", segment)
        if follow is None:
            continue
        target = segment[follow.end():].strip()
        known = re.match(
            r"(?:(?:la|le|les|un|une|des|l|the|a|an)\s+)?"
            r"(?:(?:balles?|balls?|objets?|objects?)(?:\s+(?:jaune|rouge|yellow|red))?"
            r"|(?:jaune|rouge|yellow|red)(?:\s+(?:balles?|balls?|objets?|objects?))?)\b"
            r"|(?:la|le|les|l|it|them)\b",
            target,
        )
        if known is None:
            return "unsupported_follow_target"
        suffix = target[known.end():].strip()
        numeric_suffix = re.match(
            r"\d+(?:[.,]\d+)?\s*(?:secondes?|seconds?|secs?|s|minutes?|mins?|cm|metres?|m)\b",
            fold(fr_numbers_to_digits(suffix)),
        )
        if suffix and not numeric_suffix and not re.match(
            r"(?:pendant|pour|durant|for|during|a|at|de|du|des|d|of|jusqu|until|quand|when|please|svp)\b",
            suffix,
        ):
            return "unsupported_follow_target"
    return None


def _is_unsupported_follow(step: dict[str, Any]) -> bool:
    names = {str(step.get(key, "")).strip().lower() for key in ("intent", "name", "action")}
    if not names & FOLLOW_INTENTS:
        return False
    parameters = step.get("parameters")
    if parameters is not None and not isinstance(parameters, dict):
        return True
    if not supported_follow_target(step.get("target")):
        return True
    return isinstance(parameters, dict) and not supported_follow_target(parameters.get("target_object"))


def contains_unsupported_follow_step(value: Any) -> bool:
    if isinstance(value, dict):
        return _is_unsupported_follow(value) or any(
            contains_unsupported_follow_step(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(contains_unsupported_follow_step(item) for item in value)
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


def moi_target_mismatch(text: str, step: dict[str, Any]) -> bool:
    folded = fold(text)
    params = step.get("parameters")
    return (
        (step.get("intent") or step.get("name")) in {"search_and_approach_object", "follow_person"}
        and re.search(r"\bmoi\b", folded) is not None
        and re.search(r"\b(?:jaune|yellow|rouge|red)\b", folded) is None
        and (
            step.get("target") != "face"
            or (isinstance(params, dict) and params.get("target_object", "face") != "face")
        )
    )


# intent -> (clés qui suffisent, clé ajoutée sinon, valeur ajoutée = valeur par défaut du prompt tolérée)
_DEFAULT_PARAM = {
    "move_forward": (("distance", "duration"), "duration", 1),
    "move_backward": (("distance", "duration"), "duration", 1),
    "turn_left": (("angle", "duration"), "angle", 90),
    "turn_right": (("angle", "duration"), "angle", 90),
}


def _clean_parameters(
    intent: str, params: dict, numbers: set[float], notes: list[str],
) -> tuple[dict | None, str | None]:
    """Retourne (paramètres_nettoyés, None) ou (None, raison_de_rejet) ; ajoute les notes à `notes`."""
    cleaned = {}
    allowed = ALLOWED_PARAMS.get(intent, set())
    for key, value in params.items():
        if intent in INTENT_LEXICON and key not in allowed:
            notes.append(f"{intent}.{key} inutile : supprimé")
            continue
        num = _num(value) if key in NUMERIC_KEYS else None
        if num is not None and num not in numbers:
            default = intent in _DEFAULT_PARAM and _DEFAULT_PARAM[intent][1] == key and num == _DEFAULT_PARAM[intent][2]
            if not default:
                if numbers:
                    return None, f"{intent}.{key}={value} ne correspond à aucun nombre de la phrase"
                notes.append(f"{intent}.{key}={value} absent de la phrase : supprimé")
                continue
        cleaned[key] = value
    return cleaned, None


def _sentence_position(intent: str, tokens: list[str]) -> int | None:
    rule = INTENT_LEXICON.get(intent)
    if rule is None:
        return None
    prefixes, words, _ = rule
    for index, token in enumerate(tokens):
        if token in words or any(token.startswith(p) for p in prefixes):
            return index
    return None


def _order_by_sentence(folded: str, steps: list) -> list:
    """Remet les étapes dans l'ordre de leurs mots-clés ; les étapes sans mot-clé gardent leur place."""
    tokens = folded.split()
    positions = {
        i: _sentence_position(step.get("intent") or step.get("name"), tokens)
        for i, step in enumerate(steps)
    }
    slots = [i for i, pos in positions.items() if pos is not None]
    ordered = sorted(slots, key=lambda i: positions[i])
    result = list(steps)
    for slot, src in zip(slots, ordered):
        result[slot] = steps[src]
    return result


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
    refusal = follow_request_refusal(sent_text)
    if refusal:
        return [], refusal, []
    folded = fold(sent_text)
    numbers = {float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", folded)}
    kept, notes = [], []
    for step in steps:
        if not isinstance(step, dict):
            return [], "étape invalide", notes
        intent = step.get("intent") or step.get("name")
        if moi_target_mismatch(sent_text, step):
            return [], "moi désigne le visage : target doit être face", notes
        if not _licensed(intent, folded):
            if intent == "stop":
                notes.append("stop parasite supprimé")
                continue
            return [], f"intent {intent!r} non justifié par la phrase", notes
        params = step.get("parameters")
        if isinstance(params, dict):
            cleaned, rejection = _clean_parameters(intent, params, numbers, notes)
            if rejection:
                return [], rejection, notes
            step = {**step, "parameters": cleaned}
        if intent in _DEFAULT_PARAM:
            sufficient, added_key, added_value = _DEFAULT_PARAM[intent]
            p = dict(step.get("parameters") or {})
            if not any(k in p for k in sufficient):
                p[added_key] = added_value
                step = {**step, "parameters": p}
        kept.append(step)
    reordered = _order_by_sentence(folded, kept)
    if reordered != kept:
        notes.append("étapes réordonnées selon l'ordre des verbes de la phrase")
    return reordered, None, notes
