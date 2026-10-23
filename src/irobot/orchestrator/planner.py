from __future__ import annotations

from typing import Sequence

from irobot.skills.base_skill import Skill


class SkillPlanner:
    """Planifie une séquence de skills à partir d'une intention.

    Ce squelette montre l'idée d'orchestration : on garde des tâches sous forme
    de liste de skills, dans un ordre explicite, plutôt que de laisser le LLM
    décider directement les GPIO.
    """

    def __init__(self, skills: Sequence[Skill] | None = None):
        self.skills = list(skills or [])

    def plan(self, intent: str) -> list[Skill]:
        if intent == "follow_red_ball":
            return self.skills

        if intent == "stop":
            return []

        return self.skills
