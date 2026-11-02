"""Shared runtime state and JSONL trace storage."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Any

from irobot.config.settings import load_runtime_settings
from irobot.domain.orchestrator.mission_state_machine import MissionStateMachine
from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.interfaces.intent_parser import Intent, IntentParser, IntentValidator
from irobot.interfaces.language_controller import LanguageController
from irobot.interfaces.perception_pipeline import ObjectPerceptionPipeline
from irobot.interfaces.voice_llm import LLMWarmup
from irobot.interfaces.voice_llm_transport import llm_warmup_wait_seconds


class VoiceRuntimeState:
    """One shared state for the plan and execution mixins."""

    def __init__(
        self,
        *,
        robot=None,
        camera=None,
        sensor=None,
        perception: ObjectPerceptionPipeline | None = None,
        registry: SkillRegistry | None = None,
        input_device: str = "auto",
        use_llm: bool = True,
        trace_dir: str | None = None,
        threaded: bool = True,
    ):
        self.robot = robot
        self.threaded = threaded
        self._worker: threading.Thread | None = None
        self.last_result: Any = None
        self.camera = camera
        self.sensor = sensor
        self.perception = perception
        self.input_device = input_device
        self.use_llm = use_llm
        self.settings = load_runtime_settings()
        self._emergency_event = threading.Event()
        self.trace_dir = Path(trace_dir) if trace_dir else Path.cwd() / "target" / "logs"
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.controller = LanguageController(
            robot=robot,
            camera=camera,
            sensor=sensor,
            perception=perception,
            registry=registry or SkillRegistry.default(),
        )
        self.parser = IntentParser()
        self.validator = IntentValidator()
        self.mission = MissionStateMachine()
        # Renseignés par main() : préchauffage LLM et attente bloquante en mode une seule commande.
        self.warmup: LLMWarmup | None = None
        self.wait_for_warmup = False

    def _await_warmup(self) -> str:
        """Attend le préchauffage si demandé (mode une commande) ; ne lève jamais, retourne le statut."""
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
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        return self.trace_dir / f"runtime_trace_{stamp}.jsonl"

    def _write_trace_event(self, trace_path: Path, event: dict[str, Any]) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **event,
        }
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with trace_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _intent_to_dict(self, intent: Intent) -> dict[str, Any]:
        return {
            "name": intent.name,
            "target": intent.target,
            "parameters": dict(intent.parameters),
            "confidence": intent.confidence,
            "raw_text": intent.raw_text,
        }
