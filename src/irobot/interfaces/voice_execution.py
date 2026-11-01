"""Mission sequencing, retries, deadlines and execution traces."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from irobot.domain.skills.behaviors.approach_target import ApproachTargetSkill
from irobot.interfaces.intent_parser import Intent
from irobot.interfaces.plan_guards import (
    is_pure_stop,
    follow_request_refusal,
    contains_unsupported_follow_step,
)
from irobot.interfaces.text_normalizer import preprocess
from irobot.interfaces.voice_constants import UNSUPPORTED_PLAN_SOURCES
from irobot.interfaces.voice_state import VoiceRuntimeState


class VoiceExecutionMixin(VoiceRuntimeState):
    def _step_has_failure(self, step_result: dict[str, Any]) -> bool:
        results = step_result.get("results") or []
        for result in results:
            status = getattr(result, "status", None)
            if status == "failed":
                return True
        return False

    def _step_in_progress(self, step_result: dict[str, Any]) -> bool:
        results = step_result.get("results") or []
        for result in results:
            status = getattr(result, "status", None)
            if status == "in_progress":
                return True
        return False

    def _safety_stop_reason(self, step_result: dict[str, Any]) -> str | None:
        if step_result.get("reason") == "obstacle prioritized":
            return "obstacle"
        if self._emergency_stop_requested():
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
        if intent.name in {"search_and_approach_object", "follow_red_ball", "follow_person"}:
            tracking_s = ApproachTargetSkill._to_float(
                params.get("tracking_timeout_s"), ApproachTargetSkill.DEFAULT_MAX_TRACKING_S
            )
            search_s = ApproachTargetSkill._to_float(
                params.get("search_timeout_s"), float(self.settings.search_timeout_seconds)
            )
            return max(
                base,
                max(0.1, tracking_s) + max(0.1, search_s) + float(self.settings.timeout_margin_seconds),
            )
        try:
            duration_s = float(params.get("duration_s"))
        except (TypeError, ValueError):
            return base
        search_s = self._to_float(params.get("search_timeout_s"), None)
        search_s = float(self.settings.search_timeout_seconds) if search_s is None else search_s
        return max(base, duration_s + search_s + float(self.settings.timeout_margin_seconds))

    def _effective_mission_timeout(self, intents: list[Intent]) -> float:
        total = sum(self._effective_step_timeout(intent) for intent in intents)
        return max(float(self.settings.mission_timeout_seconds), total)

    def _execute_intent_with_retry(self, intent: Intent, trace_path: Path) -> dict[str, Any]:
        max_retries = max(0, int(self.settings.max_step_retries))
        step_timeout = self._effective_step_timeout(intent)
        attempt = 0
        last_result: dict[str, Any] | None = None
        while attempt <= max_retries:
            if self._emergency_stop_requested():
                return {"intent": intent, "status": "aborted", "reason": "emergency stop"}
            step_started = time.time()
            result = self.controller.handle_intent(intent)
            duration = time.time() - step_started
            result["attempt"] = attempt + 1
            result["step_duration_seconds"] = round(duration, 4)
            self._trace_step_result(trace_path, intent, result, duration, attempt + 1)

            if self._abort_on_safety_stop(intent, result, trace_path):
                return result

            if duration > step_timeout:
                result["status"] = "aborted"
                result["reason"] = "step timeout"
                return result

            if result.get("status") == "aborted":
                return result

            if result.get("status") == "accepted" and not self._step_has_failure(result) and not self._step_in_progress(result):
                return result

            last_result = result
            attempt += 1

        if last_result is None:
            return {"intent": intent, "status": "failed", "reason": "unknown execution error"}

        last_result["status"] = "incomplete"
        last_result["reason"] = last_result.get("reason") or "max retries reached"
        return last_result

    def _trace_step_result(
        self, trace_path: Path, intent: Intent, result: dict[str, Any],
        duration: float, attempt: int,
    ) -> None:
        self._write_trace_event(trace_path, {
            "event": "step_result", "attempt": attempt,
            "intent": self._intent_to_dict(intent), "status": result.get("status"),
            "duration_seconds": round(duration, 4),
        })

    def _abort_on_safety_stop(
        self, intent: Intent, result: dict[str, Any], trace_path: Path,
    ) -> bool:
        reason = self._safety_stop_reason(result)
        if reason is None:
            return False
        result.update(status="aborted", reason=reason)
        self._write_trace_event(trace_path, {
            "event": "emergency_stop" if reason == "emergency stop" else "obstacle_stop",
            "reason": reason, "intent": self._intent_to_dict(intent),
        })
        return True

    def _handle_text_as_plan(self, text: str):
        """Traite une consigne complète en une fois via le LLM, puis exécute les étapes."""
        trace_path = self._trace_path()
        started_at = time.time()
        self._write_trace_event(trace_path, {"event": "input", "text": text})
        self.mission.reset()
        intents, plan_trace, warmup_status = self._collect_plan(text)
        if self._emergency_stop_requested():
            self.mission.abort("emergency stop")
            return {
                "input": text, "status": "aborted", "reason": "emergency stop",
                "steps": [], "trace_path": str(trace_path), "mission": self.mission.as_dict(),
            }
        refusal = self._plan_refusal(intents, plan_trace)
        if refusal is not None:
            return {"status": "rejected", "reason": refusal, "steps": []}
        self._trace_raw_plan(trace_path, intents, plan_trace, warmup_status)
        if plan_trace.get("source") in UNSUPPORTED_PLAN_SOURCES:
            return self._unsupported_plan(text, trace_path, plan_trace)
        intents, validation_errors = self._prepare_plan(text, intents, trace_path)
        if validation_errors:
            self.mission.fail("invalid plan step")
            return {
                "input": text, "status": "rejected", "reason": "invalid plan step",
                "validation_errors": validation_errors, "trace_path": str(trace_path),
                "source": plan_trace.get("source"), "mission": self.mission.as_dict(),
            }
        if not intents:
            self.mission.fail("empty plan")
            return {
                "status": "rejected", "reason": "empty plan", "input": text,
                "trace_path": str(trace_path), "source": plan_trace.get("source"),
                "mission": self.mission.as_dict(),
            }
        steps, status = self._run_plan(intents, trace_path)
        self._finish_mission(status)
        duration = round(time.time() - started_at, 4)
        self._write_trace_event(trace_path, {
            "event": "mission_result", "status": status,
            "duration_seconds": duration, "steps_count": len(steps),
        })
        return {
            "input": text, "status": status, "steps": steps,
            "validation_errors": validation_errors, "source": plan_trace.get("source"),
            "trace_path": str(trace_path), "duration_seconds": duration,
            "mission": self.mission.as_dict(),
        }

    def _collect_plan(self, text: str) -> tuple[list[Intent], dict[str, Any], str]:
        warmup_status = self.warmup.status if self.warmup is not None else "skipped"
        if is_pure_stop(text):
            # Sécurité : arrêt pur traité localement, sans LLM ni normalisation des nombres.
            intents = [Intent(name="stop", raw_text=text, confidence=1.0)]
            plan_trace = {"source": "local_stop", "llm_content": None, "llm_json": None, "normalized_text": None}
        elif (local_intent := self.parser.parse(text)).name == "follow_person":
            intents = [local_intent]
            plan_trace = {"source": "local_parser_follow_person"}
        elif self.use_llm:
            warmup_status = self._await_warmup()
            intents, plan_trace = self._ask_plan(text)
        else:
            intents = self.parser.parse_plan(text)
            plan_trace = {
                "source": "local_parser",
                "llm_content": None,
                "llm_json": None,
                "normalized_text": preprocess(text),
            }
        return intents, plan_trace, warmup_status

    def _plan_refusal(self, intents: list[Intent], plan_trace: dict[str, Any]) -> str | None:
        if plan_trace.get("source") == "llm_follow_refused":
            return plan_trace["guard_reason"]
        if any(
            follow_request_refusal(it.raw_text)
            or contains_unsupported_follow_step({
                "intent": it.name, "target": it.target, "parameters": it.parameters,
            }) for it in intents
        ):
            return "unsupported_follow_target"
        return None

    def _trace_raw_plan(
        self, trace_path: Path, intents: list[Intent],
        plan_trace: dict[str, Any], warmup_status: str,
    ) -> None:
        self._write_trace_event(
            trace_path,
            {
                "event": "plan_raw",
                "source": plan_trace.get("source"),
                "normalized_text": plan_trace.get("normalized_text"),
                "intents": [self._intent_to_dict(it) for it in intents],
                "llm_json": plan_trace.get("llm_json"),
                "llm_content": plan_trace.get("llm_content"),
                "error": plan_trace.get("error"),
                "error_type": plan_trace.get("error_type"),
                "guard_notes": plan_trace.get("guard_notes"),
                "guard_reason": plan_trace.get("guard_reason"),
                "llm_latency_seconds": plan_trace.get("llm_latency_seconds"),
                "llm_response_format": plan_trace.get("llm_response_format"),
                "llm_attempts": plan_trace.get("llm_attempts"),
                "llm_prompt_tokens": plan_trace.get("llm_prompt_tokens"),
                "llm_completion_tokens": plan_trace.get("llm_completion_tokens"),
                "llm_timings": plan_trace.get("llm_timings"),
                "warmup_status": warmup_status,
            },
        )

    def _unsupported_plan(self, text: str, trace_path: Path, plan_trace: dict[str, Any]) -> dict[str, Any]:
        self.mission.fail("unsupported command")
        self._write_trace_event(trace_path, {
            "event": "plan_unsupported", "text": text,
            "normalized_text": plan_trace.get("normalized_text"),
            "llm_content": plan_trace.get("llm_content"),
            "guard_reason": plan_trace.get("guard_reason"),
            "guard_notes": plan_trace.get("guard_notes"),
        })
        return {
            "input": text, "status": "rejected", "reason": "unsupported command",
            "guard_reason": plan_trace.get("guard_reason"), "steps": [],
            "trace_path": str(trace_path), "source": plan_trace.get("source"),
            "mission": self.mission.as_dict(),
        }

    def _prepare_plan(
        self, text: str, intents: list[Intent], trace_path: Path,
    ) -> tuple[list[Intent], list[dict[str, Any]]]:
        intents = self._normalize_plan_intent_names(intents)
        intents = self._expand_execute_path(intents)
        intents = self._expand_high_level_intents(intents)
        intents = self._expand_return_to_start(intents)

        if len(intents) > int(self.settings.max_plan_steps):
            intents = intents[: int(self.settings.max_plan_steps)]
            intents.append(Intent(name="stop", raw_text=text, confidence=1.0))

        validated_intents, validation_errors = self._validate_intent_plan(intents)
        self._write_trace_event(
            trace_path,
            {
                "event": "plan_validated",
                "intents": [self._intent_to_dict(it) for it in validated_intents],
                "validation_errors": validation_errors,
            },
        )

        return validated_intents, validation_errors

    def _run_plan(self, intents: list[Intent], trace_path: Path) -> tuple[list[dict[str, Any]], str]:
        self.mission.start(intents[0].name, intents[0].target, metadata={"steps_total": len(intents)})
        self.mission.begin_execution()
        execution_started_at = time.time()
        mission_timeout = self._effective_mission_timeout(intents)

        steps = []
        global_status = "accepted"
        try:
            for intent in intents:
                self.mission.state.metadata["step_index"] = len(steps)
                if (time.time() - execution_started_at) > mission_timeout:
                    global_status = "aborted"
                    step_result = {"intent": intent, "status": "aborted", "reason": "mission timeout"}
                    steps.append(step_result)
                    self.mission.abort("mission timeout")
                    self._write_trace_event(trace_path, {"event": "mission_timeout", "intent": self._intent_to_dict(intent)})
                    break

                step_result = self._execute_intent_with_retry(intent, trace_path)
                if step_result.get("status") == "stopped":
                    global_status = "stopped"
                    steps.append(step_result)
                    self.mission.abort("stop")
                    break
                failed = step_result.get("status") in {"rejected", "failed", "incomplete", "aborted"}
                if failed:
                    global_status = "incomplete" if step_result.get("status") != "aborted" else "aborted"
                    if global_status == "aborted":
                        self.mission.abort(step_result.get("reason", "aborted"))
                    else:
                        self.mission.fail(step_result.get("reason", "step failed"))
                steps.append(step_result)
                if failed:
                    break
        finally:
            self._safe_stop()
        return steps, global_status

    def _finish_mission(self, global_status: str) -> None:
        if self.mission.state.phase == "executing":
            if global_status == "accepted":
                self.mission.succeed()
            elif global_status == "aborted":
                self.mission.abort("aborted")
            else:
                self.mission.fail("incomplete")
