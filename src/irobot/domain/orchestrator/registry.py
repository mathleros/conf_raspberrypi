from __future__ import annotations

from collections.abc import Iterable

from irobot.domain.skills import (
    DetectObstacleSkill,
    DetectObjectSkill,
    FollowObjectSkill,
    FollowTargetSkill,
    MoveBackwardSkill,
    MoveCircleSkill,
    MoveForwardSkill,
    StopMotionSkill,
    TurnLeftSkill,
    TurnRightSkill,
)
from irobot.domain.skills.base_skill import Skill


class SkillRegistry:
    """Registre central des skills exposées par le robot.

    L'objectif est de rendre le planificateur explicite et déterministe :
    le LLM ne décide pas directement des GPIO, il formule une intention,
    et le registre retourne la liste de skills associée à cette intention.
    """

    def __init__(self, skills: Iterable[Skill] | None = None):
        self._skills: dict[str, Skill] = {}
        if skills:
            for skill in skills:
                self.register(skill)

    def register(self, skill: Skill) -> Skill:
        self._skills[skill.name] = skill
        return skill

    def register_many(self, skills: Iterable[Skill]) -> None:
        for skill in skills:
            self.register(skill)

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def get_many(self, names: Iterable[str]) -> list[Skill]:
        resolved: list[Skill] = []
        for name in names:
            skill = self.get(name)
            if skill is not None:
                resolved.append(skill)
        return resolved

    def names(self) -> list[str]:
        return sorted(self._skills)

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __iter__(self):
        return iter(self._skills.values())

    @classmethod
    def default(cls) -> "SkillRegistry":
        registry = cls()
        registry.register_many(
            [
                MoveForwardSkill(),
                MoveBackwardSkill(),
                TurnLeftSkill(),
                TurnRightSkill(),
                StopMotionSkill(),
                DetectObjectSkill(),
                DetectObstacleSkill(),
                FollowTargetSkill(),
                FollowObjectSkill(),
                MoveCircleSkill(),
            ]
        )
        return registry
