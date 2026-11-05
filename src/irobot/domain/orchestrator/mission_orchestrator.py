"""Executes a planned mission with deadlines, retries, and state transitions."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from irobot.config.settings import RuntimeSettings, load_runtime_settings
from irobot.domain.intent import Intent
from irobot.domain.numbers import to_float
from irobot.domain.orchestrator.mission_state_machine import MissionStateMachine
from irobot.domain.orchestrator.planner import SkillPlanStep
from irobot.domain.skills.behaviors.approach_target import ApproachTargetSkill
from irobot.domain.skills.behaviors.target_tracking import FOLLOW_INTENTS


@dataclass(frozen=True)
class _StepRunner:
    """Callbacks shared by every step of one mission execution."""

    execute_step: Callable[[SkillPlanStep], dict[str, Any]]
    stop_requested: Callable[[], bool]
    on_event: Callable[[dict[str, Any]], None] | None = None

    def emit(self, event: dict[str, Any]) -> None:
        if self.on_event is not None:
            self.on_event(event)


class MissionOrchestrator:
    """Runs compiled skill steps without depending on runtime or hardware interfaces."""

    def __init__(
        self,
        settings: RuntimeSettings | None = None,
        state_machine: MissionStateMachine | None = None,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self.settings = settings or load_runtime_settings()
        self.state_machine = state_machine or MissionStateMachine()
        self.time_fn = time_fn or time.monotonic

    @staticmethod
    def _step_has_failure(step_result: dict[str, Any]) -> bool:
        return any(
            getattr(result, "status", None) == "failed"
            for result in step_result.get("results") or []
        )

    @staticmethod
    def _step_in_progress(step_result: dict[str, Any]) -> bool:
        return any(
            getattr(result, "status", None) == "in_progress"
            for result in step_result.get("results") or []
        )

    def _safety_stop_reason(
        self,
        step_result: dict[str, Any],
        stop_requested: Callable[[], bool],
    ) -> str | None:
        if step_result.get("reason") == "obstacle prioritized":
            return "obstacle"
        if stop_requested():
            return "emergency stop"
        for result in step_result.get("results") or []:
            data = getattr(result, "data", None) or {}
            if data.get("emergency_stop"):
                return "emergency stop"
            if data.get("obstacle_detected") is True:
                return "obstacle"
        return None

    def _effective_step_timeout(self, intent: Intent) -> float:
        base = float(self.settings.step_timeout_seconds)
        params = intent.parameters or {}
        if intent.name in FOLLOW_INTENTS and params.get("duration_s") is None:
            return float("inf")
        if intent.name == "search_and_approach_object":
            tracking_s = to_float(
                params.get("tracking_timeout_s"), ApproachTargetSkill.DEFAULT_MAX_TRACKING_S,
            )
            search_s = to_float(
                params.get("search_timeout_s"), float(self.settings.search_timeout_seconds),
            )
            return max(
                base,
                max(0.1, tracking_s) + max(0.1, search_s) + float(self.settings.timeout_margin_seconds),
            )
        duration_s = to_float(params.get("duration_s"), require_finite=True)
        if duration_s is None:
            return base
        search_s = to_float(params.get("search_timeout_s"), require_finite=True)
        if search_s is None:
            search_s = float(self.settings.search_timeout_seconds)
        return max(base, duration_s + search_s + float(self.settings.timeout_margin_seconds))

    def _effective_mission_timeout(self, intents: Sequence[Intent]) -> float:
        total = sum(self._effective_step_timeout(intent) for intent in intents)
        return max(float(self.settings.mission_timeout_seconds), total)

    def _execute_planned_step_with_retry(
        self,
        step: SkillPlanStep,
        runner: _StepRunner,
    ) -> dict[str, Any]:
        intent = step.intent
        following = intent.name in FOLLOW_INTENTS
        max_retries = 0 if following else max(0, int(self.settings.max_step_retries))
        step_timeout = self._effective_step_timeout(intent)
        attempt = 0
        last_result: dict[str, Any] | None = None
        while attempt <= max_retries:
            if runner.stop_requested():
                return {"intent": intent, "status": "aborted", "reason": "emergency stop"}
            result = self._execute_attempt(step, runner, attempt + 1, step_timeout)
            if result.get("status") in {"aborted", "stopped"}:
                return result
            if following and (self._step_has_failure(result) or self._step_in_progress(result)):
                result.update(status="failed", reason="tracking did not complete")
                return result
            if (
                result.get("status") == "accepted"
                and not self._step_has_failure(result)
                and not self._step_in_progress(result)
            ):
                return result

            last_result = result
            attempt += 1

        if last_result is None:
            return {"intent": intent, "status": "failed", "reason": "unknown execution error"}
        last_result["status"] = "incomplete"
        last_result["reason"] = last_result.get("reason") or "max retries reached"
        return last_result

    def _execute_attempt(
        self, step: SkillPlanStep, runner: _StepRunner,
        attempt: int, step_timeout: float,
    ) -> dict[str, Any]:
        started = self.time_fn()
        result = runner.execute_step(step)
        duration = self.time_fn() - started
        result.update(attempt=attempt, step_duration_seconds=round(duration, 4))
        runner.emit({
            "event": "step_result", "intent": step.intent, "result": result,
            "duration_seconds": duration, "attempt": attempt,
        })
        reason = self._safety_stop_reason(result, runner.stop_requested)
        if reason is not None:
            result.update(status="aborted", reason=reason)
            runner.emit({
                "event": "emergency_stop" if reason == "emergency stop" else "obstacle_stop",
                "reason": reason, "intent": step.intent,
            })
        elif duration > step_timeout:
            result.update(status="aborted", reason="step timeout")
        return result

    def execute(
        self,
        planned_steps: Sequence[SkillPlanStep],
        execute_step: Callable[[SkillPlanStep], dict[str, Any]],
        *,
        stop_requested: Callable[[], bool],
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[list[dict[str, Any]], str]:
        if not planned_steps:
            raise ValueError("A mission requires at least one planned step")
        intents = [step.intent for step in planned_steps]
        self.state_machine.start(
            intents[0].name,
            intents[0].target,
            metadata={"steps_total": len(intents)},
        )
        self.state_machine.begin_execution()
        try:
            runner = _StepRunner(execute_step, stop_requested, on_event)
            steps, status = self._run_steps(planned_steps, runner)
        except Exception as exc:
            self.state_machine.fail(f"{type(exc).__name__}: {exc}")
            raise
        if self.state_machine.state.phase == "executing":
            self.state_machine.succeed()
        return steps, status

    def _run_steps(
        self, planned_steps: Sequence[SkillPlanStep], runner: _StepRunner,
    ) -> tuple[list[dict[str, Any]], str]:
        execution_started_at = self.time_fn()
        intents = [step.intent for step in planned_steps]
        mission_timeout = self._effective_mission_timeout(intents)
        steps: list[dict[str, Any]] = []
        global_status = "accepted"

        for planned_step in planned_steps:
            intent = planned_step.intent
            self.state_machine.state.metadata["step_index"] = len(steps)
            if self.time_fn() - execution_started_at > mission_timeout:
                global_status = "aborted"
                step_result = {"intent": intent, "status": "aborted", "reason": "mission timeout"}
                steps.append(step_result)
                self.state_machine.abort("mission timeout")
                runner.emit({"event": "mission_timeout", "intent": intent})
                break

            step_result = self._execute_planned_step_with_retry(planned_step, runner)
            if step_result.get("status") == "stopped":
                global_status = "stopped"
                steps.append(step_result)
                self.state_machine.abort("stop")
                break
            failed = step_result.get("status") in {"rejected", "failed", "incomplete", "aborted"}
            if failed:
                global_status = "aborted" if step_result.get("status") == "aborted" else "incomplete"
                if global_status == "aborted":
                    self.state_machine.abort(str(step_result.get("reason", "aborted")))
                else:
                    self.state_machine.fail(str(step_result.get("reason", "step failed")))
            steps.append(step_result)
            if failed:
                break

        return steps, global_status
