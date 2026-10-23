from __future__ import annotations

from irobot.skills.base_skill import Skill, SkillContext, SkillResult


class SkillExecutor:
    """Exécute une skill avec validation et gestion de résultat."""

    def __init__(self, context: SkillContext):
        self.context = context

    def run(self, skill: Skill) -> SkillResult:
        if not skill.validate(self.context):
            return SkillResult(
                status="failed",
                message=f"La skill '{skill.name}' n'est pas exécutable dans ce contexte.",
                data={"skill": skill.name},
                confidence=0.0,
                next_action=None,
            )

        result = skill.execute(self.context)
        self.context.state["last_skill_result"] = result
        return result
