"""Exécution et registre de skills, partagés par `app` et `app2`."""

from irobot.common.domain.orchestrator.executor import SkillExecutor
from irobot.common.domain.orchestrator.registry import SkillRegistry

__all__ = [
    "SkillExecutor",
    "SkillRegistry",
]
