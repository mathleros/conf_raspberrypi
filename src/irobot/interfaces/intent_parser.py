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


@dataclass
class Intent:
    """Représente une intention robotique issue du langage naturel."""

    name: str
    target: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    raw_text: str = ""


def _extract_duration(text: str) -> float | None:
    """Extrait une durée en secondes depuis une phrase libre."""
    patterns = [
        r"(?:pendant|pour|durant)\s*(\d+(?:[.,]\d+)?)\s*(?:seconde|secondes|sec|secs|s)\b",
        r"(?:for|during)\s*(\d+(?:[.,]\d+)?)\s*(?:second|seconds|sec|secs|s)\b",
        r"\b(\d+(?:[.,]\d+)?)\s*(?:s|sec|second|seconde|seconds|secondes)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return max(0.1, float(match.group(1).replace(",", ".")))
    return None


def _extract_distance(text: str) -> tuple[float, str] | None:
    """Extrait une distance (cm ou m) depuis une phrase libre."""
    patterns = [
        r"\b(\d+(?:[.,]\d+)?)\s*(cm|centim[eè]tre|centim[eè]tres)\b",
        r"\b(\d+(?:[.,]\d+)?)\s*(m|m[eè]tre|m[eè]tres)\b",
    ]
    lowered = text.lower()
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
            duration = _extract_duration(cleaned) or 1.0
            return Intent(
                name="move_forward",
                parameters={"duration": duration},
                confidence=0.88,
                raw_text=text,
            )

        if any(token in lowered for token in ["recule", "reculer", "go back", "backward", "move backward", "arriere", "arrière"]):
            duration = _extract_duration(cleaned) or 1.0
            return Intent(
                name="move_backward",
                parameters={"duration": duration},
                confidence=0.88,
                raw_text=text,
            )

        if any(token in lowered for token in ["gauche", "turn left", "left turn", "tourne à gauche", "tourne a gauche"]):
            duration = _extract_duration(cleaned) or 1.0
            return Intent(
                name="turn_left",
                parameters={"duration": duration},
                confidence=0.88,
                raw_text=text,
            )

        if any(token in lowered for token in ["droite", "turn right", "right turn", "tourne à droite", "tourne a droite"]):
            duration = _extract_duration(cleaned) or 1.0
            return Intent(
                name="turn_right",
                parameters={"duration": duration},
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


class IntentValidator:
    """Valide qu'une intention est cohérente et autorisée."""

    ALLOWED_INTENTS = {
        "follow_red_ball",
        "avoid_obstacle",
        "search_and_approach_object",
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
        if intent.name not in self.ALLOWED_INTENTS:
            return False
        if intent.name == "follow_red_ball":
            return intent.target in {None, "red_ball"}
        return True
