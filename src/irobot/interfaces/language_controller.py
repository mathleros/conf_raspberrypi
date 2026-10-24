"""Contrôleur de langage : convertit du texte ou de la voix en intention puis en plan de skills."""

from __future__ import annotations

from irobot.domain.orchestrator.executor import SkillExecutor
from irobot.domain.orchestrator.planner import SkillPlanner
from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.domain.skills.base_skill import SkillContext
from irobot.interfaces.intent_parser import Intent, IntentParser, IntentValidator
from irobot.interfaces.perception_pipeline import ObjectPerceptionPipeline


class LanguageController:
    """Pipeline complet : texte -> intention -> plan -> exécution."""

    def __init__(
        self,
        robot=None,
        camera=None,
        sensor=None,
        perception: ObjectPerceptionPipeline | None = None,
        registry: SkillRegistry | None = None,
    ):
        self.robot = robot
        self.camera = camera
        self.sensor = sensor
        self.perception = perception
        self.parser = IntentParser()
        self.validator = IntentValidator()
        self.planner = SkillPlanner(registry=registry or SkillRegistry.default())

    def _inject_perception_state(self, context: SkillContext) -> None:
        if self.perception is None:
            return
        params = context.state.get("active_intent_parameters") or {}
        target = params.get("target_object")
        detection = self.perception.detect(target=target)
        if detection is None:
            return
        context.state["last_object_position"] = detection.position
        if detection.distance_cm is not None:
            context.state["last_object_distance_cm"] = float(detection.distance_cm)
        context.state["target_object"] = detection.label

    def _should_prioritize_obstacle_stop(self, context: SkillContext, skill_name: str) -> bool:
        if context.robot is None:
            return False
        check_obstacle = getattr(context.robot, "check_obstacle", None)
        if check_obstacle is None:
            return False
        if skill_name not in {"move_forward", "move_backward", "turn_left", "turn_right", "follow_target"}:
            return False
        try:
            return bool(check_obstacle())
        except Exception:
            return False

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
            perception=self.perception,
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
            self._inject_perception_state(context)
            if self._should_prioritize_obstacle_stop(context, skill.name):
                stop_skill = self.planner.registry.get("stop_motion")
                if stop_skill is not None:
                    results.append(executor.run(stop_skill))
                return {
                    "intent": intent,
                    "status": "aborted",
                    "reason": "obstacle prioritized",
                    "plan": [skill.name for skill in plan],
                    "results": results,
                }
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
            perception=self.perception,
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
            self._inject_perception_state(context)
            if self._should_prioritize_obstacle_stop(context, skill.name):
                stop_skill = self.planner.registry.get("stop_motion")
                if stop_skill is not None:
                    results.append(executor.run(stop_skill))
                return {
                    "intent": intent,
                    "status": "aborted",
                    "reason": "obstacle prioritized",
                    "plan": [skill.name for skill in plan],
                    "results": results,
                }
            context.state["active_skill"] = skill.name
            results.append(executor.run(skill))
        return {
            "intent": intent,
            "status": "accepted",
            "plan": [skill.name for skill in plan],
            "results": results,
        }
