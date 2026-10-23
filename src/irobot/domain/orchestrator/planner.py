from __future__ import annotations

from typing import Sequence

from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.domain.skills.base_skill import Skill


class SkillPlanner:
    """Planifie une séquence de skills à partir d'une intention.

    Ce planificateur utilise un registre explicite de skills et un mapping
    intention -> séquence de skills. L'intention est ainsi transformée en
    plan déterministe au lieu d'être laissée libre.
    """

    INTENT_TO_SKILLS: dict[str, list[str]] = {
        "follow_red_ball": [
            "detect_red_ball",
            "follow_target",
            "detect_obstacle",
            "stop_motion",
        ],
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

    def __init__(self, skills: Sequence[Skill] | None = None, registry: SkillRegistry | None = None):
        self.registry = registry or SkillRegistry.default()
        if skills:
            self.registry.register_many(skills)
        self.skills = list(skills or [])

    def plan(self, intent: str) -> list[Skill]:
        names = self.INTENT_TO_SKILLS.get(intent, [])
        if not names:
            return []

        resolved = self.registry.get_many(names)
        if resolved:
            return resolved

        return self.skills

    def plan_with_target(self, intent: str, *, target: str | None = None) -> list[Skill]:
        plan = self.plan(intent)
        if target == "red_ball" and "detect_red_ball" not in {skill.name for skill in plan}:
            detect_skill = self.registry.get("detect_red_ball")
            if detect_skill is not None:
                plan.insert(0, detect_skill)
        return plan
