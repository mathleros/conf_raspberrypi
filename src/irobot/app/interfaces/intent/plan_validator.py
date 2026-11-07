"""Normalize and validate parsed intents before compiling a skill plan."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from irobot.app.domain.intent import Intent
from irobot.app.domain.intent_validator import IntentValidator
from irobot.app.interfaces.plan_guards import (
    TARGET_COLOR_SYNONYMS,
    contains_unsupported_follow_step,
    follow_request_refusal,
)
from irobot.app.interfaces.voice_constants import (
    DEFAULT_FOLLOW_DURATION_SEC,
    DEFAULT_MOVE_DURATION_SEC,
    DEFAULT_TURN_ANGLE_DEG,
    MAX_SEARCH_TIMEOUT_SEC,
    MIN_OBJECT_DURATION_SEC,
    MIN_SEARCH_TIMEOUT_SEC,
    OBJECT_INTENTS,
    PLAN_INTENT_SYNONYMS,
)
from irobot.common.config.settings import RuntimeSettings
from irobot.common.domain.numbers import to_float
from irobot.common.domain.skills.primitives.base_motion_primitive import (
    normalize_distance_unit,
)


class IntentPlanValidator:
    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings
        self.validator = IntentValidator()

    def validate(self, intents: list[Intent]) -> tuple[list[Intent], list[dict[str, Any]]]:
        sanitized: list[Intent] = []
        errors: list[dict[str, Any]] = []
        for index, intent in enumerate(intents):
            if follow_request_refusal(intent.raw_text) or not self.validator.validate(intent):
                errors.append(
                    {
                        "index": index,
                        "reason": "intent not allowed",
                        "intent": asdict(intent),
                    },
                )
                continue
            if intent.name in {"move_forward", "move_backward", "turn_left", "turn_right"}:
                intent = self._sanitize_primitive_intent(intent)
            elif intent.name in OBJECT_INTENTS:
                intent = self._sanitize_object_intent(intent)
            sanitized.append(intent)

        return sanitized, errors

    def normalize(self, intents: list[Intent]) -> list[Intent]:
        """Normalise les noms d'intents issus du LLM pour limiter les `unknown`."""
        synonyms = PLAN_INTENT_SYNONYMS
        normalized: list[Intent] = []
        for intent in intents:
            name = intent.name.strip().lower()
            mapped = synonyms.get(name, name)
            target = intent.target
            parameters = dict(intent.parameters)
            if mapped in OBJECT_INTENTS:
                target, parameters = self._normalize_object_target(mapped, target, parameters)
            normalized.append(
                Intent(
                    name=mapped,
                    target=target,
                    parameters=parameters,
                    confidence=intent.confidence,
                    raw_text=intent.raw_text,
                ),
            )
        return normalized

    @staticmethod
    def _color_from_label(value: Any) -> str | None:
        if value is None:
            return None
        return TARGET_COLOR_SYNONYMS.get(str(value).strip().lower())

    def _normalize_object_target(
        self, name: str, target: str | None, parameters: dict[str, Any],
    ) -> tuple[str | None, dict[str, Any]]:
        """Ramène les couleurs de cible (jaune, balle rouge...) à `yellow`/`red`."""
        if name == "follow_object" and contains_unsupported_follow_step({
            "intent": name, "target": target, "parameters": parameters,
        }):
            return target, parameters
        color = self._color_from_label(target)
        if color is None:
            color = self._color_from_label(parameters.get("target_object"))
        if color is not None:
            target = color
            parameters["target_object"] = color
        elif target is None and parameters.get("target_object") is not None and name == "follow_object":
            target = str(parameters["target_object"])
        return target, parameters

    def _sanitize_object_intent(self, intent: Intent) -> Intent:
        """Borne les paramètres de recherche/approche/suivi ; valeurs invalides -> défauts."""
        params = dict(intent.parameters)
        settings = self.settings

        if "stand_off_cm" in params:
            value = to_float(params["stand_off_cm"], float(settings.stand_off_default_cm), require_finite=True)
            params["stand_off_cm"] = max(
                float(settings.min_stand_off_cm), min(value, float(settings.max_stand_off_cm)),
            )
        if "duration_s" in params:
            value = to_float(params["duration_s"], DEFAULT_FOLLOW_DURATION_SEC, require_finite=True)
            params["duration_s"] = max(MIN_OBJECT_DURATION_SEC, min(value, float(settings.max_follow_duration_sec)))
        if "search_timeout_s" in params:
            value = to_float(
                params["search_timeout_s"], float(settings.search_timeout_seconds), require_finite=True,
            )
            params["search_timeout_s"] = max(MIN_SEARCH_TIMEOUT_SEC, min(value, MAX_SEARCH_TIMEOUT_SEC))

        return Intent(
            name=intent.name,
            target=intent.target,
            parameters=params,
            confidence=intent.confidence,
            raw_text=intent.raw_text,
        )

    def _sanitize_primitive_intent(self, intent: Intent) -> Intent:
        """Normalise et borne les paramètres de primitives pour un plan sûr."""
        params = dict(intent.parameters)
        if intent.name in {"move_forward", "move_backward"}:
            distance = to_float(params.get("distance"), require_finite=True)
            unit = normalize_distance_unit(params.get("unit"))
            duration = to_float(params.get("duration"), require_finite=True)

            if distance is None and duration is None:
                duration = DEFAULT_MOVE_DURATION_SEC

            if distance is not None:
                if unit == "m":
                    distance = max(0.01, min(distance, self.settings.max_distance_cm / 100.0))
                else:
                    distance = max(0.1, min(distance, self.settings.max_distance_cm))
                params["distance"] = distance
                params["unit"] = unit

            if duration is not None:
                params["duration"] = max(0.1, min(duration, self.settings.max_duration_sec))

        if intent.name in {"turn_left", "turn_right"}:
            angle = to_float(params.get("angle"), require_finite=True)
            duration = to_float(params.get("duration"), require_finite=True)
            if angle is None and duration is None and not params.get("full_rotation"):
                angle = DEFAULT_TURN_ANGLE_DEG
            if angle is not None:
                params["angle"] = max(1.0, min(angle, self.settings.max_angle_deg))
                params["unit"] = "degrees"
            if duration is not None:
                params["duration"] = max(0.1, min(duration, self.settings.max_duration_sec))

        return Intent(
            name=intent.name,
            target=intent.target,
            parameters=params,
            confidence=intent.confidence,
            raw_text=intent.raw_text,
        )
