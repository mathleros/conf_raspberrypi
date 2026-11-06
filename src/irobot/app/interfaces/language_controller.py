"""Maps validated intents to skills and executes them."""

from __future__ import annotations

import logging
from typing import Any

from irobot.app.domain.intent_validator import IntentValidator
from irobot.app.domain.orchestrator.planner import SkillPlanner, SkillPlanStep
from irobot.app.interfaces.plan_guards import follow_request_refusal
from irobot.common.config.settings import RuntimeSettings
from irobot.common.domain.orchestrator.executor import SkillExecutor
from irobot.common.domain.orchestrator.registry import SkillRegistry
from irobot.common.domain.skills.base_skill import SkillContext
from irobot.common.domain.skills.behaviors.target_tracking import FOLLOW_INTENTS
from irobot.common.domain.skills.blackboard_state import BlackboardState
from irobot.common.interfaces.perception_contracts import ObjectPerceptionPipeline


class LanguageController:
    """Executes planned intents through their associated skills."""

    def __init__(
        self,
        robot: Any | None = None,
        camera: Any | None = None,
        sensor: Any | None = None,
        perception: ObjectPerceptionPipeline | None = None,
        registry: SkillRegistry | None = None,
        settings: RuntimeSettings | None = None,
        gallery: Any | None = None,
    ):
        self.robot = robot
        self.camera = camera
        self.sensor = sensor
        self.perception = perception
        self.gallery = gallery
        self.validator = IntentValidator()
        self.planner = SkillPlanner(registry=registry or SkillRegistry.default(settings))

    def _select_face_target(self, intent) -> None:
        """Cible faciale : prénom de la galerie pour follow_person, sinon le plus grand visage."""
        set_target = getattr(self.camera, "set_face_target", None)
        if set_target is None:
            return
        name = intent.parameters.get("person") if intent.name == "follow_person" else None
        if not name or self.gallery is None:
            set_target(None, None)
            return
        canonical = self.gallery.resolve(name)
        set_target(canonical, self.gallery.get(name))

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
        if skill_name not in {"move_forward", "turn_left", "turn_right", "approach_target", "follow_object"}:
            return False
        try:
            return bool(context.robot.check_obstacle())
        except Exception:
            logging.getLogger(__name__).exception("Echec du capteur d'obstacle")
            return True

    def handle_planned_step(self, step: SkillPlanStep):
        intent = step.intent
        refusal = follow_request_refusal(intent.raw_text)
        if refusal:
            return {"intent": intent, "status": "rejected", "reason": refusal}
        if not self.validator.validate(intent):
            return {"intent": intent, "status": "rejected", "reason": "intent not allowed"}
        plan = step.skills
        if not plan:
            return {"intent": intent, "status": "rejected", "reason": "no skill plan"}
        self._select_face_target(intent)

        context = SkillContext(
            robot=self.robot,
            camera=self.camera,
            sensor=self.sensor,
            perception=self.perception,
            perception_target=intent.perception_target,
            state=BlackboardState(
                active_intent_name=intent.name,
                active_intent_parameters={
                    **intent.parameters,
                    **({"target_object": intent.target} if intent.name in FOLLOW_INTENTS and intent.target else {}),
                },
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
            results.append(executor.run(skill))
        return {
            "intent": intent,
            "status": "accepted",
            "plan": [skill.name for skill in plan],
            "results": results,
        }
