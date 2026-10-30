"""Parsing des intentions issues d'une commande vocale ou textuelle.

Le rôle de ce module est de convertir une phrase naturelle en une intention
métier structurée, puis de laisser l'orchestrateur sélectionner les skills
compatibles. Le LLM n'est pas autorisé à piloter directement les GPIO ; il
produit un `Intent` validé par le système.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from irobot.interfaces.text_normalizer import fr_numbers_to_digits
from irobot.interfaces.plan_guards import follow_request_refusal, supported_follow_target


@dataclass
class Intent:
    """Représente une intention robotique issue du langage naturel."""

    name: str
    target: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    raw_text: str = ""


_DECIMAL_RE = re.compile(r"(\d+)[.,](\d+)")
_DECIMAL_MARK = "\ue000"


def _replace_french_numbers(text: str) -> str:
    """Nombres français en lettres -> chiffres (normaliseur partagé avec le LLM), décimales préservées.

    Les conversions d'unités de `preprocess` ne sont pas appliquées : les extracteurs
    ci-dessous gèrent déjà minutes et mètres (y compris décimaux).
    """
    protected = _DECIMAL_RE.sub(rf"\1{_DECIMAL_MARK}\2", text)
    return fr_numbers_to_digits(protected).replace(_DECIMAL_MARK, ".")


def _extract_color(text: str) -> str | None:
    lowered = text.lower()
    if re.search(r"\b(?:jaune|yellow)\b", lowered):
        return "yellow"
    if re.search(r"\b(?:rouge|red)\b", lowered):
        return "red"
    return None


def _extract_duration(text: str) -> float | None:
    """Extrait une durée en secondes (secondes ou minutes) depuis une phrase libre."""
    lowered = _replace_french_numbers(text.lower())
    total = 0.0
    found = False

    minutes = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:minutes?|mins?)\b", lowered)
    if minutes:
        total += float(minutes.group(1).replace(",", ".")) * 60.0
        found = True

    patterns = [
        r"(?:pendant|pour|durant)\s*(\d+(?:[.,]\d+)?)\s*(?:seconde|secondes|sec|secs|s)\b",
        r"(?:for|during)\s*(\d+(?:[.,]\d+)?)\s*(?:second|seconds|sec|secs|s)\b",
        r"\b(\d+(?:[.,]\d+)?)\s*(?:s|sec|second|seconde|seconds|secondes)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            total += float(match.group(1).replace(",", "."))
            found = True
            break

    return max(0.1, total) if found else None


def _extract_distance(text: str) -> tuple[float, str] | None:
    """Extrait une distance (cm ou m) depuis une phrase libre."""
    patterns = [
        r"\b(\d+(?:[.,]\d+)?)\s*(cm|centim[eè]tre|centim[eè]tres)\b",
        r"\b(\d+(?:[.,]\d+)?)\s*(m|m[eè]tre|m[eè]tres)\b",
    ]
    lowered = _replace_french_numbers(text.lower())
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        value = float(match.group(1).replace(",", "."))
        unit = match.group(2)
        if unit.startswith("cm") or unit.startswith("centim"):
            return (max(0.1, value), "cm")
        return (max(0.01, value), "m")
    return None


def _extract_angle(text: str) -> float | None:
    """Extrait un angle en degrés (« de 45 degrés », « quatre vingt dix degrés »)."""
    lowered = _replace_french_numbers(text.lower())
    match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:°|degr[eé]s?|deg)(?:\b|$)", lowered)
    if match:
        return float(match.group(1).replace(",", "."))
    return None


def _motion_parameters(text: str) -> dict[str, Any]:
    """Avance/recul : durée explicite, sinon distance, sinon 1 s par défaut."""
    duration = _extract_duration(text)
    if duration is not None:
        return {"duration": duration}
    distance = _extract_distance(text)
    if distance is not None:
        return {"distance": distance[0], "unit": distance[1]}
    return {"duration": 1.0}


def _turn_parameters(text: str) -> dict[str, Any]:
    """Rotation : durée explicite, sinon angle, sinon 90°."""
    duration = _extract_duration(text)
    if duration:
        return {"duration": duration}
    angle = _extract_angle(text)
    return {"angle": angle if angle is not None else 90, "unit": "degrees"}


def _extract_stand_off_cm(text: str) -> float | None:
    """Extrait une distance d'approche (« à 1 m », « à 50 cm ») convertie en cm."""
    lowered = _replace_french_numbers(text.lower())
    match = re.search(
        r"(?:\bà|\ba|\bde|\bat)\s+(\d+(?:[.,]\d+)?)\s*(cm|centim[eè]tres?|m[eè]tres?|m)\b", lowered
    )
    if match:
        value = float(match.group(1).replace(",", "."))
        return value if match.group(2).startswith(("cm", "centim")) else value * 100.0
    distance = _extract_distance(text)
    if distance is None:
        return None
    return distance[0] if distance[1] == "cm" else distance[0] * 100.0


def _extract_target_object(text: str) -> str | None:
    """Extrait un nom d'objet simple depuis une phrase (heuristique légère)."""
    lowered = text.lower()
    patterns = [
        r"(?:objet|object)\s+(?:de type\s+)?([a-z0-9_\-éèêàùïîç]+)",
        r"(?:cherche|trouve|détecte|detecte|approche)\s+(?:un|une|le|la|l')?\s*([a-z0-9_\-éèêàùïîç]+)",
    ]
    forbidden = {
        "objet",
        "object",
        "toi",
        "point",
        "départ",
        "depart",
        "puis",
        "ensuite",
        "et",
        "de",
        "du",
        "la",
        "le",
        "les",
        "un",
        "une",
    }
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            token = match.group(1).strip(" '-")
            if token and token not in forbidden:
                return token
    return None


class IntentParser:
    """Transforme du texte libre en intention métier structurée."""

    def parse(self, text: str) -> Intent:
        cleaned = (text or "").strip()
        if not cleaned:
            return Intent(name="unknown", raw_text=text)

        lowered = cleaned.lower()
        refusal = follow_request_refusal(cleaned)
        if refusal:
            return Intent(
                name="follow_person" if refusal == "human_capability_unavailable" else "unknown",
                raw_text=text,
            )

        # "arrête-toi quand tu vois X" est une condition d'arrêt, pas un ordre d'arrêt immédiat.
        has_condition = any(
            token in lowered for token in ["quand", "jusqu", "dès que", "des que", "lorsque", "when", "until"]
        )
        has_search_verb = any(token in lowered for token in ["tourne", "cherche", "recherche", "scan", "look"])
        if has_condition and has_search_verb:
            color = "yellow" if any(t in lowered for t in ["jaune", "yellow"]) else (
                "red" if any(t in lowered for t in ["rouge", "red"]) else None
            )
            return Intent(
                name="search_and_approach_object",
                target=color,
                parameters={"search": True, "approach": False, **({"target_object": color} if color else {})},
                confidence=0.8,
                raw_text=text,
            )

        if any(token in lowered for token in ["stop", "arrêt", "arrete", "halt", "pause"]):
            return Intent(name="stop", confidence=0.95, raw_text=text)

        if any(token in lowered for token in ["retour au point de départ", "reviens au point de départ", "point de départ", "point de depart"]):
            return Intent(name="return_to_start", confidence=0.9, raw_text=text)

        if re.search(r"\b(?:suis|suit|suivre|suivez|follow)\b", lowered):
            color = _extract_color(lowered)
            parameters: dict[str, Any] = {}
            if color:
                parameters["target_object"] = color
            duration_s = _extract_duration(cleaned)
            if duration_s is not None:
                parameters["duration_s"] = duration_s
            stand_off_cm = _extract_stand_off_cm(cleaned)
            if stand_off_cm is not None:
                parameters["stand_off_cm"] = stand_off_cm
            return Intent(
                name="follow_object",
                target=color,
                parameters=parameters,
                confidence=0.88,
                raw_text=text,
            )

        if any(token in lowered for token in ["tour sur toi", "tourne sur toi", "rotation complète", "rotation complete", "360"]):
            return Intent(
                name="spin_360",
                parameters={"angle": 360, "unit": "degrees"},
                confidence=0.9,
                raw_text=text,
            )

        if any(token in lowered for token in ["carré", "carre", "forme un carré", "forme un carre"]):
            distance = _extract_distance(cleaned)
            side = distance[0] if distance else 40.0
            unit = distance[1] if distance else "cm"
            return Intent(
                name="move_square",
                parameters={"side": side, "unit": unit, "turn_direction": "right"},
                confidence=0.86,
                raw_text=text,
            )

        if any(token in lowered for token in ["contourne", "contourner", "évite l'objet", "evite l'objet", "évite objet", "evite objet"]):
            distance = _extract_distance(cleaned)
            parameters: dict[str, Any] = {"direction": "right", "clearance": 20.0, "unit": "cm"}
            if distance:
                parameters["clearance"] = distance[0]
                parameters["unit"] = distance[1]
            return Intent(
                name="contour_obstacle",
                parameters=parameters,
                confidence=0.84,
                raw_text=text,
            )

        if any(
            token in lowered
            for token in [
                "détecte", "detecte", "chercher un objet", "cherche un objet", "trouve un objet",
                "approche l'objet", "approcher l'objet", "s'en approcher", "s en approcher",
                "detect and approach", "find object", "approach object",
            ]
        ):
            target_object = _extract_target_object(cleaned)
            parameters: dict[str, Any] = {"search": True, "approach": True}
            if target_object:
                parameters["target_object"] = target_object
            return Intent(
                name="search_and_approach_object",
                target=target_object,
                parameters=parameters,
                confidence=0.87,
                raw_text=text,
            )

        color = _extract_color(lowered)
        has_approach_verb = re.search(r"\b(?:approche|approcher|rapproche|rapprocher)\b", lowered)
        has_search_verb_local = re.search(r"\b(?:cherche|chercher|recherche|trouve|look for|find)\b", lowered)
        if has_approach_verb or (color == "yellow" and has_search_verb_local):
            parameters = {"search": True, "approach": True}
            if color:
                parameters["target_object"] = color
            stand_off_cm = _extract_stand_off_cm(cleaned) if has_approach_verb else None
            if stand_off_cm is not None:
                parameters["stand_off_cm"] = stand_off_cm
            return Intent(
                name="search_and_approach_object",
                target=color,
                parameters=parameters,
                confidence=0.87,
                raw_text=text,
            )

        if any(token in lowered for token in ["balle rouge", "rouge", "cible rouge", "red ball"]):
            return Intent(
                name="follow_red_ball",
                target="red_ball",
                parameters={"speed": 0.5},
                confidence=0.9,
                raw_text=text,
            )

        if any(token in lowered for token in ["évite", "evite", "avoid", "obstacle"]):
            return Intent(
                name="avoid_obstacle",
                parameters={"speed": 0.4},
                confidence=0.85,
                raw_text=text,
            )

        if any(token in lowered for token in ["avance", "avancer", "go forward", "forward", "move forward", "va tout droit"]):
            return Intent(
                name="move_forward",
                parameters=_motion_parameters(cleaned),
                confidence=0.88,
                raw_text=text,
            )

        if any(token in lowered for token in ["recule", "reculer", "go back", "backward", "move backward", "arriere", "arrière"]):
            return Intent(
                name="move_backward",
                parameters=_motion_parameters(cleaned),
                confidence=0.88,
                raw_text=text,
            )

        if any(token in lowered for token in ["gauche", "turn left", "left turn", "tourne à gauche", "tourne a gauche"]):
            return Intent(
                name="turn_left",
                parameters=_turn_parameters(cleaned),
                confidence=0.88,
                raw_text=text,
            )

        if any(token in lowered for token in ["droite", "turn right", "right turn", "tourne à droite", "tourne a droite"]):
            return Intent(
                name="turn_right",
                parameters=_turn_parameters(cleaned),
                raw_text=text,
            )

        if any(token in lowered for token in ["cherche", "recherche", "look for", "find"]):
            return Intent(
                name="follow_red_ball",
                target="red_ball",
                confidence=0.7,
                raw_text=text,
            )

        return Intent(name="unknown", confidence=0.0, raw_text=text)

    _SEGMENT_SPLIT_RE = re.compile(r"\s*(?:(?<!\d),(?!\d)|\bet puis\b|\bpuis\b|\bensuite\b)\s*")
    _PRONOUN_RE = re.compile(r"\b(?:la|le|l'|lui)\b|-(?:la|le|lui)\b")

    def parse_plan(self, text: str) -> list[Intent]:
        """Découpe une phrase composée en segments et retourne la liste d'intents ordonnée."""
        if follow_request_refusal(text):
            return [self.parse(text)]
        segments = [seg for seg in self._SEGMENT_SPLIT_RE.split((text or "").strip()) if seg.strip()]
        if len(segments) <= 1:
            return [self.parse(text)]

        plan: list[Intent] = []
        last_target: str | None = None
        last_stand_off: float | None = None
        for segment in segments:
            intent = self.parse(segment)
            intent.raw_text = text
            lowered = segment.lower()

            # « cherche la balle rouge » suivi d'une approche/suivi : recherche, pas poursuite directe.
            if intent.name == "follow_red_ball" and re.search(r"\b(?:cherche|recherche)\b", lowered):
                intent = Intent(
                    name="search_and_approach_object",
                    target="red",
                    parameters={"search": True, "approach": True, "target_object": "red"},
                    confidence=intent.confidence,
                    raw_text=text,
                )

            if intent.name in {"search_and_approach_object", "follow_object"}:
                if intent.target is None and last_target and self._PRONOUN_RE.search(lowered):
                    intent.target = last_target
                    intent.parameters["target_object"] = last_target
                if intent.name == "follow_object" and "stand_off_cm" not in intent.parameters and last_stand_off:
                    intent.parameters["stand_off_cm"] = last_stand_off
                if intent.target in {"yellow", "red"}:
                    last_target = intent.target
                if "stand_off_cm" in intent.parameters:
                    last_stand_off = float(intent.parameters["stand_off_cm"])

            previous = plan[-1] if plan else None
            if (
                previous is not None
                and previous.name == intent.name == "search_and_approach_object"
                and (previous.target is None or intent.target is None or previous.target == intent.target)
            ):
                previous.parameters.update(intent.parameters)
                previous.target = intent.target or previous.target
                previous.confidence = min(previous.confidence, intent.confidence)
                continue
            plan.append(intent)

        return plan


class IntentValidator:
    """Valide qu'une intention est cohérente et autorisée."""

    ALLOWED_INTENTS = {
        "follow_red_ball",
        "avoid_obstacle",
        "search_and_approach_object",
        "follow_object",
        "contour_obstacle",
        "spin_360",
        "move_square",
        "return_to_start",
        "move_forward",
        "move_backward",
        "turn_left",
        "turn_right",
        "stop",
    }

    def validate(self, intent: Intent) -> bool:
        if follow_request_refusal(intent.raw_text) or intent.name in {"follow_person", "resume_follow_person"}:
            return False
        if intent.name not in self.ALLOWED_INTENTS:
            return False
        if intent.name == "follow_red_ball":
            return (intent.target in {None, "red_ball"}
                    and supported_follow_target(intent.parameters.get("target_object")))
        if intent.name == "follow_object":
            return (intent.target in {None, "red", "yellow"}
                    and supported_follow_target(intent.parameters.get("target_object")))
        return True
