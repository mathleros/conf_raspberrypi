"""Maps validated intents to skills and executes them."""

from __future__ import annotations

import logging

from irobot.domain.orchestrator.executor import SkillExecutor
from irobot.domain.orchestrator.planner import SkillPlanStep, SkillPlanner
from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.domain.intent import Intent
from irobot.domain.skills.blackboard_state import BlackboardState
from irobot.domain.skills.base_skill import SkillContext
from irobot.domain.skills.behaviors.target_tracking import FOLLOW_INTENTS
from irobot.domain.intent_validator import IntentValidator
from irobot.interfaces.perception_contracts import ObjectPerceptionPipeline
from irobot.interfaces.plan_guards import follow_request_refusal


class LanguageController:
    """Executes planned intents through their associated skills."""

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
        self.validator = IntentValidator()
        self.planner = SkillPlanner(registry=registry or SkillRegistry.default())

    def _inject_perception_state(self, context: SkillContext) -> None:
        if self.perception is None or context.perception_target is None:
            return
        detection = self.perception.detect(target=context.perception_target)
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
        if skill_name not in {"move_forward", "turn_left", "turn_right", "approach_target", "follow_object"}:
            return False
        try:
            return bool(check_obstacle())
        except Exception:
            logging.getLogger(__name__).exception("Echec du capteur d'obstacle")
            return True

    def handle_intent(self, intent: Intent):
        rejection = self._intent_rejection(intent)
        if rejection is not None:
            return rejection
        skills = self.planner.plan(intent.name)
        return self._execute_planned_step(SkillPlanStep(intent, tuple(skills)))

    def handle_planned_step(self, step: SkillPlanStep):
        rejection = self._intent_rejection(step.intent)
        if rejection is not None:
            return rejection
        return self._execute_planned_step(step)

    def _intent_rejection(self, intent: Intent):
        refusal = follow_request_refusal(intent.raw_text)
        if refusal:
            return {"intent": intent, "status": "rejected", "reason": refusal}
        if not self.validator.validate(intent):
            return {"intent": intent, "status": "rejected", "reason": "intent not allowed"}
        return None

    def _execute_planned_step(self, step: SkillPlanStep):
        intent = step.intent
        plan = step.skills
        if not plan:
            return {"intent": intent, "status": "rejected", "reason": "no skill plan"}

        context = SkillContext(
            robot=self.robot,
            camera=self.camera,
            sensor=self.sensor,
            perception=self.perception,
            perception_target=intent.perception_target,
            state=BlackboardState(
                active_intent=intent,
                active_intent_name=intent.name,
                active_intent_parameters={
                    **intent.parameters,
                    **({"target_object": intent.target} if intent.name in FOLLOW_INTENTS and intent.target else {}),
                },
                last_camera_position=None,
                last_object_position=None,
                last_ball_position=None,
                camera_ready=self.camera is not None,
            ),
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
