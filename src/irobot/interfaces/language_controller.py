"""Contrôleur de langage : convertit du texte ou de la voix en intention puis en plan de skills."""

from __future__ import annotations

from irobot.domain.orchestrator.executor import SkillExecutor
from irobot.domain.orchestrator.planner import SkillPlanner
from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.domain.skills.base_skill import SkillContext
from irobot.interfaces.intent_parser import Intent, IntentParser, IntentValidator


class LanguageController:
    """Pipeline complet : texte -> intention -> plan -> exécution."""

    def __init__(self, robot=None, camera=None, sensor=None, registry: SkillRegistry | None = None):
        self.robot = robot
        self.camera = camera
        self.sensor = sensor
        self.parser = IntentParser()
        self.validator = IntentValidator()
        self.planner = SkillPlanner(registry=registry or SkillRegistry.default())

    def handle_text(self, text: str):
        intent = self.parser.parse(text)
        if not self.validator.validate(intent):
            return {"intent": intent, "status": "rejected", "reason": "intent not allowed"}

        plan = self.planner.plan(intent.name)
        if not plan:
            return {"intent": intent, "status": "rejected", "reason": "no skill plan"}

        context = SkillContext(
            robot=self.robot,
            camera=self.camera,
            sensor=self.sensor,
            state={
                "active_intent": intent,
                "active_intent_name": intent.name,
                "active_intent_parameters": dict(intent.parameters),
                "last_camera_position": None,
                "last_object_position": None,
                "last_ball_position": None,
                "camera_ready": self.camera is not None,
            },
        )

        executor = SkillExecutor(context)
        results = []
        for skill in plan:
            context.state["active_skill"] = skill.name
            result = executor.run(skill)
            results.append(result)
            if result.next_action:
                break

        return {
            "intent": intent,
            "status": "accepted",
            "plan": [skill.name for skill in plan],
            "results": results,
        }

    def handle_intent(self, intent: Intent):
        if not self.validator.validate(intent):
            return {"intent": intent, "status": "rejected", "reason": "intent not allowed"}

        plan = self.planner.plan(intent.name)
        if not plan:
            return {"intent": intent, "status": "rejected", "reason": "no skill plan"}

        context = SkillContext(
            robot=self.robot,
            camera=self.camera,
            sensor=self.sensor,
            state={
                "active_intent": intent,
                "active_intent_name": intent.name,
                "active_intent_parameters": dict(intent.parameters),
                "last_camera_position": None,
                "last_object_position": None,
                "last_ball_position": None,
                "camera_ready": self.camera is not None,
            },
        )

        executor = SkillExecutor(context)
        results = []
        for skill in plan:
            context.state["active_skill"] = skill.name
            results.append(executor.run(skill))
        return {
            "intent": intent,
            "status": "accepted",
            "plan": [skill.name for skill in plan],
            "results": results,
        }
