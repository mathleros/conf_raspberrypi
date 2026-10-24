"""Runtime vocal complet : Vosk + LLM + intention + exécution de skills.

Ce point d'entrée transforme la parole en texte, puis en `Intent`, puis en plan
complet de skills validé par `LanguageController`. Le LLM n'est pas autorisé à
piloter les GPIO directement : il ne produit qu'une intention structurée et
validée par le système.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import requests

try:
    import vosk  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - macOS/tests
    vosk = None

from irobot.config.settings import RuntimeSettings, load_runtime_settings
from irobot.domain.orchestrator.mission_state_machine import MissionStateMachine
from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.hardware.audio.audio_utils import resolve_input_device
from irobot.interfaces.intent_parser import Intent, IntentParser, IntentValidator
from irobot.interfaces.language_controller import LanguageController
from irobot.interfaces.perception_pipeline import ObjectPerceptionPipeline

RATE = 16000
MODEL_PATH = os.path.expanduser("~/models/vosk-model-small-fr-0.22")
LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL = "ministral-3-3b"
LLM_CONNECT_TIMEOUT_SECONDS = 1.0
LLM_READ_TIMEOUT_SECONDS = 4.0
LLM_HTTP_TIMEOUT = (LLM_CONNECT_TIMEOUT_SECONDS, LLM_READ_TIMEOUT_SECONDS)
RUNTIME_SETTINGS: RuntimeSettings = load_runtime_settings()
MAX_PLAN_STEPS = RUNTIME_SETTINGS.max_plan_steps
MAX_DISTANCE_CM = RUNTIME_SETTINGS.max_distance_cm
MAX_ANGLE_DEG = RUNTIME_SETTINGS.max_angle_deg
MAX_DURATION_SEC = RUNTIME_SETTINGS.max_duration_sec
SYSTEM_PROMPT = (
    "Tu es un interprète de commande robotique. "
    "Réponds UNIQUEMENT en JSON valide avec les clés suivantes : "
    "intent, target, parameters, confidence. "
    "Les intents autorisées sont : follow_red_ball, search_and_approach_object, avoid_obstacle, "
    "move_forward, move_backward, turn_left, turn_right, stop."
)

SYSTEM_PROMPT_PLAN = (
    "Tu es un planificateur de commandes robotiques. "
    "Tu reçois une instruction potentiellement composée. "
    "Réponds UNIQUEMENT en JSON valide au format: "
    "{\"steps\": [{\"intent\": str, \"target\": str|null, \"parameters\": object, \"confidence\": float}]}. "
    "Découpe la consigne en étapes atomiques ordonnées. "
    "Tu peux utiliser: "
    "(a) des intents atomiques (follow_red_ball, search_and_approach_object, avoid_obstacle, move_forward, move_backward, turn_left, turn_right, stop, return_to_start), "
    "ou (b) un intent execute_path avec parameters.steps=[{action, distance?, unit?, angle?, duration?}] "
    "où action est uniquement dans {move_forward, move_backward, turn_left, turn_right, stop}. "
    "Si la consigne contient un retour au point de départ, utilise explicitement return_to_start."
)


@contextmanager
def _arecord_stream(device: str):
    """Ouvre un flux arecord et garantit son arrêt même en cas d'exception."""
    args = [
        "arecord",
        "-D",
        device,
        "-f",
        "S16_LE",
        "-r",
        str(RATE),
        "-c",
        "1",
        "-t",
        "raw",
    ]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    try:
        if proc.stdout is None:
            raise RuntimeError("Impossible d'ouvrir le flux audio arecord.")
        yield proc.stdout
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.0)
        if proc.stdout is not None:
            proc.stdout.close()


def transcribe_loop(device: str):
    """Lit le flux brut du microphone et le transmet à Vosk."""
    if vosk is None:
        raise RuntimeError("La dépendance 'vosk' est absente. Installez les paquets Raspberry Pi requis.")

    model = vosk.Model(MODEL_PATH)
    recognizer = vosk.KaldiRecognizer(model, RATE)
    print(f"(parle dans le micro — device: {device} — Ctrl+C pour quitter)\n", flush=True)

    bytes_per_chunk = 8000
    with _arecord_stream(device) as audio_stream:
        while True:
            raw = audio_stream.read(bytes_per_chunk)
            if not raw:
                break
            if recognizer.AcceptWaveform(raw):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()
                if text:
                    yield text
                    recognizer.Reset()


def _parse_llm_json_payload(content: str) -> dict[str, Any] | None:
    """Extrait un objet JSON depuis une réponse LLM, y compris si elle est entourée de backticks."""
    cleaned = content.strip()
    if not cleaned:
        return None
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned.split("\n", 1)[1].strip() if "\n" in cleaned else cleaned[4:].strip()
    try:
        payload = json.loads(cleaned)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    return None


def ask_llm_for_intent(text: str) -> Intent:
    """Demande un JSON de type Intent au LLM local, puis reconstruit l'objet Intent."""
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
        "max_tokens": 256,
        "stream": False,
    }
    try:
        response = requests.post(LLM_URL, json=payload, timeout=LLM_HTTP_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        parsed = _parse_llm_json_payload(content)
        if not parsed:
            return IntentParser().parse(text)

        intent_name = str(parsed.get("intent") or parsed.get("name") or "unknown").strip()
        target = parsed.get("target")
        parameters = parsed.get("parameters") or {}
        confidence = float(parsed.get("confidence") or 0.0)
        return Intent(
            name=intent_name,
            target=str(target) if target is not None else None,
            parameters=dict(parameters),
            confidence=max(0.0, min(1.0, confidence)),
            raw_text=text,
        )
    except Exception:
        return IntentParser().parse(text)


def ask_llm_for_intent_plan_with_trace(text: str) -> tuple[list[Intent], dict[str, Any]]:
    """Demande au LLM un plan ordonné d'intentions et retourne des métadonnées de trace."""
    local_fallback = IntentParser().parse(text)

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_PLAN},
            {"role": "user", "content": text},
        ],
        "temperature": 0.1,
        "max_tokens": 512,
        "stream": False,
    }
    try:
        response = requests.post(LLM_URL, json=payload, timeout=LLM_HTTP_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        parsed = _parse_llm_json_payload(content)
        if not parsed:
            return [local_fallback], {
                "source": "local_parser_fast_fallback",
                "llm_content": content,
                "llm_json": None,
            }

        raw_steps = parsed.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            return [local_fallback], {
                "source": "local_parser_fast_fallback",
                "llm_content": content,
                "llm_json": parsed,
            }

        intents: list[Intent] = []
        for step in raw_steps:
            if not isinstance(step, dict):
                continue
            intent_name = str(step.get("intent") or step.get("name") or "unknown").strip()
            target = step.get("target")
            parameters = step.get("parameters") or {}
            confidence = float(step.get("confidence") or 0.0)
            intents.append(
                Intent(
                    name=intent_name,
                    target=str(target) if target is not None else None,
                    parameters=dict(parameters),
                    confidence=max(0.0, min(1.0, confidence)),
                    raw_text=text,
                )
            )

        if not intents:
            return [local_fallback], {
                "source": "local_parser_fast_fallback",
                "llm_content": content,
                "llm_json": parsed,
            }

        return intents, {
            "source": "llm_plan",
            "llm_content": content,
            "llm_json": parsed,
        }
    except Exception:
        return [local_fallback], {
            "source": "local_parser_fast_fallback",
            "llm_content": None,
            "llm_json": None,
        }


def ask_llm_for_intent_plan(text: str) -> list[Intent]:
    """Compatibilité : retourne uniquement la liste d'intents planifiées."""
    intents, _ = ask_llm_for_intent_plan_with_trace(text)
    return intents


class VoiceRuntime:
    """Pipeline complet : microphone -> Vosk -> Intent -> LanguageController -> skills."""

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
    ):
        self.robot = robot
        self.camera = camera
        self.sensor = sensor
        self.perception = perception
        self.input_device = input_device
        self.use_llm = use_llm
        self.settings = load_runtime_settings()
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

    def _validate_intent_plan(self, intents: list[Intent]) -> tuple[list[Intent], list[dict[str, Any]]]:
        sanitized: list[Intent] = []
        errors: list[dict[str, Any]] = []
        for index, intent in enumerate(intents):
            if not self.validator.validate(intent):
                errors.append(
                    {
                        "index": index,
                        "reason": "intent not allowed",
                        "intent": self._intent_to_dict(intent),
                    }
                )
                continue
            if intent.name in {"move_forward", "move_backward", "turn_left", "turn_right"}:
                intent = self._sanitize_primitive_intent(intent)
            sanitized.append(intent)

        return sanitized, errors

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

    def _execute_intent_with_retry(self, intent: Intent, trace_path: Path) -> dict[str, Any]:
        max_retries = max(0, int(self.settings.max_step_retries))
        attempt = 0
        last_result: dict[str, Any] | None = None
        while attempt <= max_retries:
            step_started = time.time()
            result = self.controller.handle_intent(intent)
            duration = time.time() - step_started
            result["attempt"] = attempt + 1
            result["step_duration_seconds"] = round(duration, 4)
            self._write_trace_event(
                trace_path,
                {
                    "event": "step_result",
                    "attempt": attempt + 1,
                    "intent": self._intent_to_dict(intent),
                    "status": result.get("status"),
                    "duration_seconds": round(duration, 4),
                },
            )

            if duration > float(self.settings.step_timeout_seconds):
                result["status"] = "aborted"
                result["reason"] = "step timeout"
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

    def _resolve_intent(self, text: str) -> Intent:
        if not self.use_llm:
            return self.parser.parse(text)

        llm_intent = ask_llm_for_intent(text)
        if self.validator.validate(llm_intent):
            return llm_intent
        return self.parser.parse(text)

    def _expand_return_to_start(self, intents: list[Intent]) -> list[Intent]:
        """Remplace `return_to_start` par la séquence inverse des actions déjà planifiées."""
        reverse_map = {
            "move_forward": "move_backward",
            "move_backward": "move_forward",
            "turn_left": "turn_right",
            "turn_right": "turn_left",
        }
        reversible_names = set(reverse_map)
        history: list[Intent] = []
        expanded: list[Intent] = []

        for intent in intents:
            if intent.name == "return_to_start":
                for previous in reversed(history):
                    reverse_name = reverse_map.get(previous.name)
                    if reverse_name is None:
                        continue
                    expanded.append(
                        Intent(
                            name=reverse_name,
                            target=previous.target,
                            parameters=dict(previous.parameters),
                            confidence=previous.confidence,
                            raw_text=previous.raw_text,
                        )
                    )
                continue

            expanded.append(intent)
            if intent.name in reversible_names:
                history.append(intent)

        return expanded

    def _normalize_plan_intent_names(self, intents: list[Intent]) -> list[Intent]:
        """Normalise les noms d'intents issus du LLM pour limiter les `unknown`."""
        synonyms = {
            "contourner_obstacle": "contour_obstacle",
            "contourne_obstacle": "contour_obstacle",
            "avoid": "avoid_obstacle",
            "find_object": "search_and_approach_object",
            "search_object": "search_and_approach_object",
            "detect_object": "search_and_approach_object",
            "approach_object": "search_and_approach_object",
            "rotate_360": "spin_360",
            "spin": "spin_360",
            "square": "move_square",
            "path": "execute_path",
            "trajectory": "execute_path",
            "trajet": "execute_path",
            "go_home": "return_to_start",
            "back_to_start": "return_to_start",
        }
        normalized: list[Intent] = []
        for intent in intents:
            name = intent.name.strip().lower()
            mapped = synonyms.get(name, name)
            normalized.append(
                Intent(
                    name=mapped,
                    target=intent.target,
                    parameters=dict(intent.parameters),
                    confidence=intent.confidence,
                    raw_text=intent.raw_text,
                )
            )
        return normalized

    def _to_float(self, value: Any, default: float | None = None) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _sanitize_primitive_intent(self, intent: Intent) -> Intent:
        """Normalise et borne les paramètres de primitives pour un plan sûr."""
        params = dict(intent.parameters)
        if intent.name in {"move_forward", "move_backward"}:
            distance = self._to_float(params.get("distance"), None)
            unit = str(params.get("unit", "cm")).lower()
            duration = self._to_float(params.get("duration"), None)

            if distance is not None:
                if unit == "m":
                    distance = max(0.01, min(distance, self.settings.max_distance_cm / 100.0))
                else:
                    unit = "cm"
                    distance = max(0.1, min(distance, self.settings.max_distance_cm))
                params["distance"] = distance
                params["unit"] = unit

            if duration is not None:
                params["duration"] = max(0.1, min(duration, self.settings.max_duration_sec))

        if intent.name in {"turn_left", "turn_right"}:
            angle = self._to_float(params.get("angle"), None)
            duration = self._to_float(params.get("duration"), None)
            if angle is not None:
                params["angle"] = max(1.0, min(angle, self.settings.max_angle_deg))
                params["unit"] = "degrees"
            if duration is not None:
                params["duration"] = max(0.1, min(duration, self.settings.max_duration_sec))

        return Intent(
            name=intent.name,
            target=intent.target,
            parameters=params,
            confidence=intent.confidence,
            raw_text=intent.raw_text,
        )

    def _expand_execute_path(self, intents: list[Intent]) -> list[Intent]:
        """Décompose l'intent générique `execute_path` en primitives validables."""
        action_synonyms = {
            "forward": "move_forward",
            "move": "move_forward",
            "backward": "move_backward",
            "back": "move_backward",
            "left": "turn_left",
            "right": "turn_right",
        }
        allowed_actions = {"move_forward", "move_backward", "turn_left", "turn_right", "stop"}
        expanded: list[Intent] = []

        for intent in intents:
            if intent.name != "execute_path":
                expanded.append(intent)
                continue

            steps = intent.parameters.get("steps")
            if not isinstance(steps, list) or not steps:
                expanded.append(Intent(name="unknown", raw_text=intent.raw_text, parameters={"reason": "empty execute_path"}))
                continue

            for raw_step in steps[:MAX_PLAN_STEPS]:
                if not isinstance(raw_step, dict):
                    expanded.append(Intent(name="unknown", raw_text=intent.raw_text, parameters={"reason": "invalid step format"}))
                    continue

                action_raw = str(raw_step.get("action") or raw_step.get("intent") or raw_step.get("name") or "").strip().lower()
                action = action_synonyms.get(action_raw, action_raw)
                if action not in allowed_actions:
                    expanded.append(
                        Intent(
                            name="unknown",
                            raw_text=intent.raw_text,
                            parameters={"reason": "invalid action", "action": action_raw},
                        )
                    )
                    continue

                step_params = raw_step.get("parameters") if isinstance(raw_step.get("parameters"), dict) else {}
                merged_params = dict(step_params)
                for key in ("distance", "unit", "angle", "duration"):
                    if key in raw_step and key not in merged_params:
                        merged_params[key] = raw_step[key]

                primitive_intent = Intent(
                    name=action,
                    target=intent.target,
                    parameters=merged_params,
                    confidence=float(raw_step.get("confidence") or intent.confidence or 0.0),
                    raw_text=intent.raw_text,
                )
                expanded.append(self._sanitize_primitive_intent(primitive_intent))

        return expanded

    def _expand_high_level_intents(self, intents: list[Intent]) -> list[Intent]:
        """Décompose certains intents haut niveau en primitives exécutables."""
        def _to_float(value: Any, default: float) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        expanded: list[Intent] = []
        for intent in intents:
            if intent.name == "spin_360":
                for _ in range(4):
                    expanded.append(
                        Intent(
                            name="turn_right",
                            target=intent.target,
                            parameters={"angle": 90, "unit": "degrees"},
                            confidence=intent.confidence,
                            raw_text=intent.raw_text,
                        )
                    )
                continue

            if intent.name == "move_square":
                side = _to_float(intent.parameters.get("side", intent.parameters.get("distance", 40.0)), 40.0)
                unit = str(intent.parameters.get("unit", "cm"))
                direction = str(intent.parameters.get("turn_direction", "right")).lower()
                turn_intent = "turn_left" if direction == "left" else "turn_right"
                for _ in range(4):
                    expanded.append(
                        Intent(
                            name="move_forward",
                            target=intent.target,
                            parameters={"distance": side, "unit": unit},
                            confidence=intent.confidence,
                            raw_text=intent.raw_text,
                        )
                    )
                    expanded.append(
                        Intent(
                            name=turn_intent,
                            target=intent.target,
                            parameters={"angle": 90, "unit": "degrees"},
                            confidence=intent.confidence,
                            raw_text=intent.raw_text,
                        )
                    )
                continue

            if intent.name == "contour_obstacle":
                clearance = _to_float(intent.parameters.get("clearance", intent.parameters.get("distance", 20.0)), 20.0)
                unit = str(intent.parameters.get("unit", "cm"))
                expanded.extend(
                    [
                        Intent(
                            name="turn_right",
                            target=intent.target,
                            parameters={"angle": 45, "unit": "degrees"},
                            confidence=intent.confidence,
                            raw_text=intent.raw_text,
                        ),
                        Intent(
                            name="move_forward",
                            target=intent.target,
                            parameters={"distance": clearance, "unit": unit},
                            confidence=intent.confidence,
                            raw_text=intent.raw_text,
                        ),
                        Intent(
                            name="turn_left",
                            target=intent.target,
                            parameters={"angle": 90, "unit": "degrees"},
                            confidence=intent.confidence,
                            raw_text=intent.raw_text,
                        ),
                        Intent(
                            name="move_forward",
                            target=intent.target,
                            parameters={"distance": clearance, "unit": unit},
                            confidence=intent.confidence,
                            raw_text=intent.raw_text,
                        ),
                        Intent(
                            name="turn_right",
                            target=intent.target,
                            parameters={"angle": 45, "unit": "degrees"},
                            confidence=intent.confidence,
                            raw_text=intent.raw_text,
                        ),
                    ]
                )
                continue

            if intent.name in {"turn_right", "turn_left"} and bool(intent.parameters.get("full_rotation")):
                for _ in range(4):
                    expanded.append(
                        Intent(
                            name=intent.name,
                            target=intent.target,
                            parameters={"angle": 90, "unit": "degrees"},
                            confidence=intent.confidence,
                            raw_text=intent.raw_text,
                        )
                    )
                continue

            expanded.append(intent)
        return [self._sanitize_primitive_intent(it) if it.name in {"move_forward", "move_backward", "turn_left", "turn_right"} else it for it in expanded]

    def handle_text(self, text: str):
        intent = self._resolve_intent(text)
        if not self.validator.validate(intent):
            return {"intent": intent, "status": "rejected", "reason": "intent not allowed"}
        return self.controller.handle_intent(intent)

    def handle_text_as_plan(self, text: str):
        """Traite une consigne complète en une fois via le LLM, puis exécute les étapes."""
        trace_path = self._trace_path()
        started_at = time.time()
        self._write_trace_event(trace_path, {"event": "input", "text": text})
        self.mission.reset()

        if self.use_llm:
            intents, plan_trace = ask_llm_for_intent_plan_with_trace(text)
        else:
            intents = [self.parser.parse(text)]
            plan_trace = {"source": "local_parser", "llm_content": None, "llm_json": None}

        self._write_trace_event(
            trace_path,
            {
                "event": "plan_raw",
                "source": plan_trace.get("source"),
                "intents": [self._intent_to_dict(it) for it in intents],
                "llm_json": plan_trace.get("llm_json"),
            },
        )

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

        if validation_errors and not validated_intents:
            self.mission.fail("no valid plan step")
            return {
                "input": text,
                "status": "rejected",
                "reason": "no valid plan step",
                "validation_errors": validation_errors,
                "trace_path": str(trace_path),
                "source": plan_trace.get("source"),
                "mission": self.mission.as_dict(),
            }

        intents = validated_intents
        if not intents:
            self.mission.fail("empty plan")
            return {
                "status": "rejected",
                "reason": "empty plan",
                "input": text,
                "trace_path": str(trace_path),
                "source": plan_trace.get("source"),
                "mission": self.mission.as_dict(),
            }

        self.mission.start(intents[0].name, intents[0].target, metadata={"steps_total": len(intents)})
        self.mission.begin_execution()
        execution_started_at = time.time()

        steps = []
        global_status = "accepted"
        for intent in intents:
            self.mission.state.metadata["step_index"] = len(steps)
            if (time.time() - execution_started_at) > float(self.settings.mission_timeout_seconds):
                global_status = "aborted"
                step_result = {"intent": intent, "status": "aborted", "reason": "mission timeout"}
                steps.append(step_result)
                self.mission.abort("mission timeout")
                self._write_trace_event(trace_path, {"event": "mission_timeout", "intent": self._intent_to_dict(intent)})
                break

            step_result = self._execute_intent_with_retry(intent, trace_path)
            if step_result.get("status") in {"rejected", "failed", "incomplete", "aborted"}:
                global_status = "incomplete" if step_result.get("status") != "aborted" else "aborted"
                if global_status == "aborted":
                    self.mission.abort(step_result.get("reason", "aborted"))
                else:
                    self.mission.fail(step_result.get("reason", "step failed"))
            steps.append(step_result)

        if self.mission.state.phase == "executing":
            if global_status == "accepted":
                self.mission.succeed()
            elif global_status == "aborted":
                self.mission.abort("aborted")
            else:
                self.mission.fail("incomplete")

        duration = round(time.time() - started_at, 4)
        self._write_trace_event(
            trace_path,
            {
                "event": "mission_result",
                "status": global_status,
                "duration_seconds": duration,
                "steps_count": len(steps),
            },
        )

        return {
            "input": text,
            "status": global_status,
            "steps": steps,
            "validation_errors": validation_errors,
            "source": plan_trace.get("source"),
            "trace_path": str(trace_path),
            "duration_seconds": duration,
            "mission": self.mission.as_dict(),
        }

    def listen_once(self):
        device = resolve_input_device(self.input_device)
        for text in transcribe_loop(device):
            print(f"\n[VOIX] {text}", flush=True)
            result = self.handle_text(text)
            print(f"[RUNTIME] {result}", flush=True)
            return result
        return {"status": "no_transcript"}

    def listen_forever(self):
        device = resolve_input_device(self.input_device)
        try:
            for text in transcribe_loop(device):
                print(f"\n[VOIX] {text}", flush=True)
                result = self.handle_text(text)
                print(f"[RUNTIME] {result}", flush=True)
        except KeyboardInterrupt:
            print("\nInterruption clavier : arrêt du runtime vocal.")


def main():
    parser = argparse.ArgumentParser(
        description="Runtime vocal complet : Vosk → intent → skills -> robot."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Ecoute une seule phrase puis s'arrête.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Utilise le parseur local au lieu du LLM pour interpréter la commande.",
    )
    parser.add_argument(
        "--input-device",
        default="auto",
        choices=["auto", "bluetooth", "wm8960", "default"],
        help="Source audio utilisée pour l'enregistrement.",
    )
    args = parser.parse_args()

    try:
        runtime = VoiceRuntime(input_device=args.input_device, use_llm=not args.no_llm)
        if args.once:
            runtime.listen_once()
            return
        runtime.listen_forever()
    except RuntimeError as exc:
        print(f"Erreur : {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
