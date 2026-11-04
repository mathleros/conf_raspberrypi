from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from irobot.config.settings import load_runtime_settings
from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.domain.intent import Intent
from irobot.domain.skills.base_skill import Skill

MAX_PLAN_STEPS = load_runtime_settings().max_plan_steps


@dataclass(frozen=True)
class SkillPlanStep:
    """One validated intent paired with the skills that implement it."""

    intent: Intent
    skills: tuple[Skill, ...]


class SkillPlanner:
    """Expands intents into executable steps and resolves their registered skills."""

    INTENT_TO_SKILLS: dict[str, list[str]] = {
        "follow_person": ["follow_object"],
        "follow_red_ball": ["follow_object"],
        "search_and_approach_object": [
            "detect_object",
            "approach_target",
            "detect_obstacle",
            "stop_motion",
        ],
        "follow_object": ["follow_object"],
        "move_forward": ["move_forward"],
        "move_backward": ["move_backward"],
        "turn_left": ["turn_left"],
        "turn_right": ["turn_right"],
        "move_circle": [
            "turn_left",
            "move_forward",
            "stop_motion",
        ],
        "stop": ["stop_motion"],
        "avoid_obstacle": [
            "detect_obstacle",
            "stop_motion",
            "turn_left",
            "move_forward",
        ],
    }

    def __init__(self, registry: SkillRegistry | None = None):
        self.registry = registry or SkillRegistry.default()

    def plan(self, intent: str) -> list[Skill]:
        return self.registry.get_many(self.INTENT_TO_SKILLS.get(intent, []))

    def expand_intents(self, intents: Sequence[Intent]) -> list[Intent]:
        """Lower compound intents to an ordered sequence of executable intents."""
        expanded = self._expand_execute_path(list(intents))
        expanded = self._expand_high_level_intents(expanded)
        return self._expand_return_to_start(expanded)

    def plan_intents(self, intents: Sequence[Intent]) -> list[SkillPlanStep]:
        """Compile executable intents into typed intent-to-skills plan steps."""
        return [
            SkillPlanStep(intent=intent, skills=tuple(self.plan(intent.name)))
            for intent in intents
        ]

    def _expand_return_to_start(self, intents: list[Intent]) -> list[Intent]:
        reverse_map = {
            "move_forward": "move_backward",
            "move_backward": "move_forward",
            "turn_left": "turn_right",
            "turn_right": "turn_left",
        }
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
            if intent.name in reverse_map:
                history.append(intent)
        return expanded

    def _expand_execute_path(self, intents: list[Intent]) -> list[Intent]:
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
                expanded.append(
                    Intent(name="unknown", raw_text=intent.raw_text, parameters={"reason": "empty execute_path"})
                )
                continue
            for raw_step in steps[:MAX_PLAN_STEPS]:
                expanded.append(self._path_step(intent, raw_step, action_synonyms, allowed_actions))
        return expanded

    @staticmethod
    def _path_step(
        intent: Intent,
        raw_step: Any,
        synonyms: dict[str, str],
        allowed: set[str],
    ) -> Intent:
        if not isinstance(raw_step, dict):
            return Intent(
                name="unknown",
                raw_text=intent.raw_text,
                parameters={"reason": "invalid step format"},
            )
        action_raw = str(
            raw_step.get("action") or raw_step.get("intent") or raw_step.get("name") or ""
        ).strip().lower()
        action = synonyms.get(action_raw, action_raw)
        if action not in allowed:
            return Intent(
                name="unknown",
                raw_text=intent.raw_text,
                parameters={"reason": "invalid action", "action": action_raw},
            )
        step_params = raw_step.get("parameters")
        merged_params = dict(step_params) if isinstance(step_params, dict) else {}
        for key in ("distance", "unit", "angle", "duration"):
            if key in raw_step and key not in merged_params:
                merged_params[key] = raw_step[key]
        return Intent(
            name=action,
            target=intent.target,
            parameters=merged_params,
            confidence=float(raw_step.get("confidence") or intent.confidence or 0.0),
            raw_text=intent.raw_text,
        )

    def _expand_high_level_intents(self, intents: list[Intent]) -> list[Intent]:
        return [step for intent in intents for step in self._high_level_steps(intent)]

    @staticmethod
    def _derived_intent(intent: Intent, name: str, parameters: dict[str, Any]) -> Intent:
        return Intent(
            name=name,
            target=intent.target,
            parameters=parameters,
            confidence=intent.confidence,
            raw_text=intent.raw_text,
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
        return [
            self._derived_intent(intent, direction, {"angle": 90, "unit": "degrees"})
            for _ in range(4)
        ]

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
