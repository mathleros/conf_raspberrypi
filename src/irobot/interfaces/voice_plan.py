"""Deterministic normalization, expansion and validation of voice plans."""

from __future__ import annotations

import math
from typing import Any

from irobot.config.settings import load_runtime_settings
from irobot.domain.skills.primitives.base_motion_primitive import normalize_distance_unit
from irobot.interfaces.intent_parser import Intent
from irobot.interfaces.plan_guards import contains_unsupported_follow_step, TARGET_COLOR_SYNONYMS
from irobot.interfaces.voice_constants import (
    DEFAULT_MOVE_DURATION_SEC,
    DEFAULT_TURN_ANGLE_DEG,
    PLAN_INTENT_SYNONYMS,
    OBJECT_INTENTS,
    DEFAULT_STAND_OFF_CM,
    DEFAULT_FOLLOW_DURATION_SEC,
    MIN_OBJECT_DURATION_SEC,
    MIN_SEARCH_TIMEOUT_SEC,
    MAX_SEARCH_TIMEOUT_SEC,
)
from irobot.interfaces.voice_state import VoiceRuntimeState

MAX_PLAN_STEPS = load_runtime_settings().max_plan_steps


class VoicePlanMixin(VoiceRuntimeState):
    def _validate_intent_plan(self, intents: list[Intent]) -> tuple[list[Intent], list[dict[str, Any]]]:
        sanitized: list[Intent] = []
        errors: list[dict[str, Any]] = []
        for index, intent in enumerate(intents):
            if not self.validator.validate(intent):
                errors.append(
                    {
                        "index": index,
                        "reason": "intent not allowed",
                        "intent": self._intent_to_dict(intent),
                    }
                )
                continue
            if intent.name in {"move_forward", "move_backward", "turn_left", "turn_right"}:
                intent = self._sanitize_primitive_intent(intent)
            elif intent.name in OBJECT_INTENTS:
                intent = self._sanitize_object_intent(intent)
            sanitized.append(intent)

        return sanitized, errors

    def _expand_return_to_start(self, intents: list[Intent]) -> list[Intent]:
        """Remplace `return_to_start` par la séquence inverse des actions déjà planifiées."""
        reverse_map = {
            "move_forward": "move_backward",
            "move_backward": "move_forward",
            "turn_left": "turn_right",
            "turn_right": "turn_left",
        }
        reversible_names = set(reverse_map)
        history: list[Intent] = []
        expanded: list[Intent] = []

        for intent in intents:
            if intent.name == "return_to_start":
                for previous in reversed(history):
                    reverse_name = reverse_map.get(previous.name)
                    if reverse_name is None:
                        continue
                    expanded.append(
                        Intent(
                            name=reverse_name,
                            target=previous.target,
                            parameters=dict(previous.parameters),
                            confidence=previous.confidence,
                            raw_text=previous.raw_text,
                        )
                    )
                continue

            expanded.append(intent)
            if intent.name in reversible_names:
                history.append(intent)

        return expanded

    def _normalize_plan_intent_names(self, intents: list[Intent]) -> list[Intent]:
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
                )
            )
        return normalized

    @staticmethod
    def _color_from_label(value: Any) -> str | None:
        if value is None:
            return None
        return TARGET_COLOR_SYNONYMS.get(str(value).strip().lower())

    def _normalize_object_target(
        self, name: str, target: str | None, parameters: dict[str, Any]
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

    def _to_float(self, value: Any, default: float | None = None) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default

    def _sanitize_object_intent(self, intent: Intent) -> Intent:
        """Borne les paramètres de recherche/approche/suivi ; valeurs invalides -> défauts."""
        params = dict(intent.parameters)
        settings = self.settings

        if "stand_off_cm" in params:
            value = self._to_float(params["stand_off_cm"], DEFAULT_STAND_OFF_CM)
            params["stand_off_cm"] = max(
                float(settings.min_stand_off_cm), min(value, float(settings.max_stand_off_cm))
            )
        if "duration_s" in params:
            value = self._to_float(params["duration_s"], DEFAULT_FOLLOW_DURATION_SEC)
            params["duration_s"] = max(MIN_OBJECT_DURATION_SEC, min(value, float(settings.max_follow_duration_sec)))
        if "search_timeout_s" in params:
            value = self._to_float(params["search_timeout_s"], float(settings.search_timeout_seconds))
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
            distance = self._to_float(params.get("distance"), None)
            unit = normalize_distance_unit(params.get("unit"))
            duration = self._to_float(params.get("duration"), None)

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
            angle = self._to_float(params.get("angle"), None)
            duration = self._to_float(params.get("duration"), None)
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

    def _expand_execute_path(self, intents: list[Intent]) -> list[Intent]:
        """Décompose l'intent générique `execute_path` en primitives validables."""
        action_synonyms = {
            "forward": "move_forward",
            "move": "move_forward",
            "backward": "move_backward",
            "back": "move_backward",
            "left": "turn_left",
            "right": "turn_right",
        }
        allowed_actions = {"move_forward", "move_backward", "turn_left", "turn_right", "stop"}
        expanded: list[Intent] = []

        for intent in intents:
            if intent.name != "execute_path":
                expanded.append(intent)
                continue

            steps = intent.parameters.get("steps")
            if not isinstance(steps, list) or not steps:
                expanded.append(Intent(name="unknown", raw_text=intent.raw_text, parameters={"reason": "empty execute_path"}))
                continue

            for raw_step in steps[:MAX_PLAN_STEPS]:
                expanded.append(self._path_step(intent, raw_step, action_synonyms, allowed_actions))
        return expanded

    def _path_step(
        self, intent: Intent, raw_step: Any,
        synonyms: dict[str, str], allowed: set[str],
    ) -> Intent:
        if not isinstance(raw_step, dict):
            return Intent(name="unknown", raw_text=intent.raw_text,
                          parameters={"reason": "invalid step format"})
        action_raw = str(raw_step.get("action") or raw_step.get("intent") or raw_step.get("name") or "").strip().lower()
        action = synonyms.get(action_raw, action_raw)
        if action not in allowed:
            return Intent(name="unknown", raw_text=intent.raw_text,
                          parameters={"reason": "invalid action", "action": action_raw})
        step_params = raw_step.get("parameters")
        merged_params = dict(step_params) if isinstance(step_params, dict) else {}
        for key in ("distance", "unit", "angle", "duration"):
            if key in raw_step and key not in merged_params:
                merged_params[key] = raw_step[key]
        primitive = Intent(
            name=action, target=intent.target, parameters=merged_params,
            confidence=float(raw_step.get("confidence") or intent.confidence or 0.0),
            raw_text=intent.raw_text,
        )
        return self._sanitize_primitive_intent(primitive)

    def _expand_high_level_intents(self, intents: list[Intent]) -> list[Intent]:
        """Décompose certains intents haut niveau en primitives exécutables."""
        expanded: list[Intent] = []
        for intent in intents:
            expanded.extend(self._high_level_steps(intent))
        return [self._sanitize_primitive_intent(it) if it.name in {"move_forward", "move_backward", "turn_left", "turn_right"} else it for it in expanded]

    @staticmethod
    def _derived_intent(intent: Intent, name: str, parameters: dict[str, Any]) -> Intent:
        return Intent(
            name=name, target=intent.target, parameters=parameters,
            confidence=intent.confidence, raw_text=intent.raw_text,
        )

    @staticmethod
    def _high_level_number(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _high_level_steps(self, intent: Intent) -> list[Intent]:
        params = intent.parameters
        if intent.name == "spin_360":
            return self._rotation_steps(intent, "turn_right")
        if intent.name in {"turn_right", "turn_left"} and bool(params.get("full_rotation")):
            return self._rotation_steps(intent, intent.name)
        if intent.name == "move_square":
            side = self._high_level_number(params.get("side", params.get("distance", 40.0)), 40.0)
            unit = str(params.get("unit", "cm"))
            direction = str(params.get("turn_direction", "right")).lower()
            turn = "turn_left" if direction == "left" else "turn_right"
            return [
                self._derived_intent(intent, name, values)
                for _ in range(4)
                for name, values in (
                    ("move_forward", {"distance": side, "unit": unit}),
                    (turn, {"angle": 90, "unit": "degrees"}),
                )
            ]
        if intent.name == "contour_obstacle":
            return self._contour_steps(intent)
        return [intent]

    def _rotation_steps(self, intent: Intent, direction: str) -> list[Intent]:
        return [self._derived_intent(intent, direction, {"angle": 90, "unit": "degrees"})
                for _ in range(4)]

    def _contour_steps(self, intent: Intent) -> list[Intent]:
        params = intent.parameters
        clearance = self._high_level_number(params.get("clearance", params.get("distance", 20.0)), 20.0)
        unit = str(params.get("unit", "cm"))
        actions = (
            ("turn_right", {"angle": 45, "unit": "degrees"}),
            ("move_forward", {"distance": clearance, "unit": unit}),
            ("turn_left", {"angle": 90, "unit": "degrees"}),
            ("move_forward", {"distance": clearance, "unit": unit}),
            ("turn_right", {"angle": 45, "unit": "degrees"}),
        )
        return [self._derived_intent(intent, name, dict(values)) for name, values in actions]
