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


class IntentParser:
    """Transforme du texte libre en intention métier structurée."""

    def parse(self, text: str) -> Intent:
        cleaned = (text or "").strip()
        if not cleaned:
            return Intent(name="unknown", raw_text=text)

        lowered = cleaned.lower()

        if any(token in lowered for token in ["stop", "arrêt", "arrete", "halt", "pause"]):
            return Intent(name="stop", confidence=0.95, raw_text=text)

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
