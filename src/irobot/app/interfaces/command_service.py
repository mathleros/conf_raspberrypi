"""Application entry point: parse, validate, compile, and submit commands."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from irobot.app.domain.intent import Intent
from irobot.app.domain.orchestrator.mission_orchestrator import MissionOrchestrator
from irobot.app.domain.orchestrator.planner import SkillPlanStep
from irobot.common.config.settings import RuntimeSettings, load_runtime_settings
from irobot.common.domain.orchestrator.registry import SkillRegistry
from irobot.app.interfaces.intent.intent_parser import IntentPlanParser
from irobot.app.interfaces.intent.llm_intent_parser import (
    LLMWarmup,
    ask_llm_for_intent_plan_with_trace,
)
from irobot.app.interfaces.intent.plan_validator import IntentPlanValidator
from irobot.app.interfaces.intent.text_intent_parser import TextIntentParser
from irobot.app.interfaces.language_controller import LanguageController
from irobot.common.interfaces.perception_contracts import ObjectPerceptionPipeline
from irobot.app.interfaces.plan_guards import (
    contains_unsupported_follow_step,
    follow_request_refusal,
    is_pure_stop,
)
from irobot.common.interfaces.text_normalizer import preprocess
from irobot.app.interfaces.voice_constants import UNSUPPORTED_PLAN_SOURCES
from irobot.app.interfaces.voice_llm_transport import llm_warmup_wait_seconds


class CommandService:
    """Composes language adapters, plan validation, and mission execution."""

    def __init__(
        self, *, robot=None, camera=None, sensor=None,
        perception: ObjectPerceptionPipeline | None = None,
        registry: SkillRegistry | None = None,
        use_llm: bool = True,
        trace_dir: str | None = None,
        settings: RuntimeSettings | None = None,
    ) -> None:
        self.robot = robot
        self.use_llm = use_llm
        self.settings = settings or load_runtime_settings()
        self._emergency_event = threading.Event()
        self.trace_dir = Path(trace_dir) if trace_dir else Path.cwd() / "target" / "logs"
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.controller = LanguageController(
            robot=robot, camera=camera, sensor=sensor,
            perception=perception, registry=registry, settings=self.settings,
        )
        self.planner = self.controller.planner
        self.parser: IntentPlanParser = TextIntentParser()
        self.plan_validator = IntentPlanValidator(self.settings)
        self.mission_orchestrator = MissionOrchestrator(settings=self.settings)
        self.warmup: LLMWarmup | None = None
        self.wait_for_warmup = False

    @property
    def emergency_event(self) -> threading.Event:
        return self._emergency_event

    def _ask_plan(self, text: str) -> tuple[list[Intent], dict[str, Any]]:
        return ask_llm_for_intent_plan_with_trace(text)

    def _emergency_stop_requested(self) -> bool:
        if self._emergency_event.is_set():
            return True
        detector = getattr(self.robot, "emergency_stop_requested", None)
        if not callable(detector):
            return False
        try:
            return bool(detector())
        except Exception:
            logging.getLogger(__name__).exception("Impossible de lire l'arret d'urgence")
            return True

    def safe_stop(self) -> None:
        stop = getattr(self.robot, "stop", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                logging.getLogger(__name__).exception("Impossible d'arreter le robot")

    def _await_warmup(self) -> str:
        if self.warmup is None:
            return "skipped"
        if not self.wait_for_warmup:
            return self.warmup.status
        wait_seconds = llm_warmup_wait_seconds()
        if self.warmup.status == "running":
            print(f"[LLM] Préchauffage du modèle en cours (attente max {wait_seconds:g}s)...", flush=True)
        status = self.warmup.wait(wait_seconds)
        if status == "timeout":
            print(f"[LLM] Préchauffage non terminé après {wait_seconds:g}s, envoi de la commande quand même.", flush=True)
        elif status == "failed":
            print("[LLM] Préchauffage en échec, envoi de la commande quand même.", flush=True)
        return status

    def _trace_path(self) -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return self.trace_dir / f"runtime_trace_{stamp}.jsonl"

    def _write_trace_event(self, trace_path: Path, event: dict[str, Any]) -> None:
        payload = {"timestamp": datetime.now(UTC).isoformat(), **event}
        with trace_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _trace_mission_event(self, trace_path: Path, event: dict[str, Any]) -> None:
        event_type = event["event"]
        intent = event["intent"]
        if event_type == "step_result":
            result = event["result"]
            self._write_trace_event(trace_path, {
                "event": event_type,
                "attempt": event["attempt"],
                "intent": asdict(intent),
                "status": result.get("status"),
                "duration_seconds": round(event["duration_seconds"], 4),
                "results": [
                    {"status": item.status, "message": item.message, "data": item.data}
                    for item in result.get("results") or []
                ],
            })
        elif event_type in {"emergency_stop", "obstacle_stop"}:
            self._write_trace_event(trace_path, {
                "event": event_type,
                "reason": event["reason"],
                "intent": asdict(intent),
            })
        else:
            self._write_trace_event(trace_path, {
                "event": event_type,
                "intent": asdict(intent),
            })

    def handle_text(self, text: str) -> dict[str, Any]:
        """Parse, validates, plans, and executes a complete text command."""
        trace_path = self._trace_path()
        started_at = time.time()
        self._write_trace_event(trace_path, {"event": "input", "text": text})
        mission = self.mission_orchestrator.state_machine
        mission.reset()
        intents, plan_trace, warmup_status = self._collect_plan(text)
        if self._emergency_stop_requested():
            mission.abort("emergency stop")
            return {
                "input": text, "status": "aborted", "reason": "emergency stop",
                "steps": [], "trace_path": str(trace_path), "mission": mission.as_dict(),
            }
        refusal = self._plan_refusal(intents, plan_trace)
        if refusal is not None:
            return {"status": "rejected", "reason": refusal, "steps": []}
        self._trace_raw_plan(trace_path, intents, plan_trace, warmup_status)
        if plan_trace.get("source") in UNSUPPORTED_PLAN_SOURCES:
            return self._unsupported_plan(text, trace_path, plan_trace)
        planned_steps, validation_errors = self._prepare_plan(text, intents, trace_path)
        if validation_errors:
            mission.fail("invalid plan step")
            return {
                "input": text, "status": "rejected", "reason": "invalid plan step",
                "validation_errors": validation_errors, "trace_path": str(trace_path),
                "source": plan_trace.get("source"), "mission": mission.as_dict(),
            }
        if not planned_steps:
            mission.fail("empty plan")
            return {
                "status": "rejected", "reason": "empty plan", "input": text,
                "trace_path": str(trace_path), "source": plan_trace.get("source"),
                "mission": mission.as_dict(),
            }
        return self._execute_plan(text, planned_steps, validation_errors, plan_trace, trace_path, started_at)

    def _execute_plan(
        self, text: str, planned_steps: list[SkillPlanStep],
        validation_errors: list[dict[str, Any]], plan_trace: dict[str, Any],
        trace_path: Path, started_at: float,
    ) -> dict[str, Any]:
        try:
            steps, status = self.mission_orchestrator.execute(
                planned_steps, self.controller.handle_planned_step,
                stop_requested=self._emergency_stop_requested,
                on_event=lambda event: self._trace_mission_event(trace_path, event),
            )
        finally:
            self.safe_stop()
        duration = round(time.time() - started_at, 4)
        self._write_trace_event(trace_path, {
            "event": "mission_result", "status": status,
            "duration_seconds": duration, "steps_count": len(steps),
        })
        return {
            "input": text, "status": status, "steps": steps,
            "validation_errors": validation_errors, "source": plan_trace.get("source"),
            "trace_path": str(trace_path), "duration_seconds": duration,
            "mission": self.mission_orchestrator.state_machine.as_dict(),
        }

    def _collect_plan(self, text: str) -> tuple[list[Intent], dict[str, Any], str]:
        warmup_status = self.warmup.status if self.warmup is not None else "skipped"
        if is_pure_stop(text):
            # Sécurité : arrêt pur traité localement, sans LLM ni normalisation des nombres.
            intents = [Intent(name="stop", raw_text=text, confidence=1.0)]
            plan_trace = {"source": "local_stop", "llm_content": None, "llm_json": None, "normalized_text": None}
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
                "intents": [asdict(it) for it in intents],
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
        mission = self.mission_orchestrator.state_machine
        mission.fail("unsupported command")
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
            "mission": mission.as_dict(),
        }

    def _prepare_plan(
        self, text: str, intents: list[Intent], trace_path: Path,
    ) -> tuple[list[SkillPlanStep], list[dict[str, Any]]]:
        intents = self.plan_validator.normalize(intents)
        intents = self.planner.expand_intents(intents)

        if len(intents) > int(self.settings.max_plan_steps):
            intents = intents[: int(self.settings.max_plan_steps)]
            intents.append(Intent(name="stop", raw_text=text, confidence=1.0))

        validated_intents, validation_errors = self.plan_validator.validate(intents)
        planned_steps = self.planner.plan_intents(validated_intents)
        self._write_trace_event(
            trace_path,
            {
                "event": "plan_validated",
                "intents": [asdict(it) for it in validated_intents],
                "validation_errors": validation_errors,
            },
        )
        self._write_trace_event(
            trace_path,
            {
                "event": "plan_compiled",
                "steps": [
                    {
                        "intent": asdict(step.intent),
                        "skills": [skill.name for skill in step.skills],
                    }
                    for step in planned_steps
                ],
            },
        )

        return planned_steps, validation_errors
