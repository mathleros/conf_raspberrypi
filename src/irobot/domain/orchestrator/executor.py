from __future__ import annotations

from irobot.domain.skills.base_skill import Skill, SkillContext, SkillResult


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

        validate_result = getattr(self.context.robot, "is_protected_result_current", None)
        if callable(validate_result):
            self.context.state["last_skill_result"] = None
        if callable(validate_result) and not validate_result():
            return SkillResult(
                status="failed", message="Contexte invalidé par la supervision.",
                data={"protection_fault": True}, confidence=0.0,
            )
        result = skill.execute(self.context)
        if callable(validate_result) and not validate_result():
            return SkillResult(
                status="failed", message="Résultat invalidé par la supervision.",
                data={"protection_fault": True}, confidence=0.0,
            )
        self.context.state["last_skill_result"] = result
        return result
