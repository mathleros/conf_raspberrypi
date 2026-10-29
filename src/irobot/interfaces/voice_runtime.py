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
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any

import requests

try:
    import vosk  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - macOS/tests
    vosk = None

from irobot.config.settings import RuntimeSettings, load_llm_settings, load_runtime_settings
from irobot.domain.orchestrator.mission_state_machine import MissionStateMachine
from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.domain.skills.primitives.base_motion_primitive import normalize_distance_unit
from irobot.hardware.audio.audio_utils import resolve_input_device
from irobot.interfaces.intent_parser import Intent, IntentParser, IntentValidator
from irobot.interfaces.language_controller import LanguageController
from irobot.interfaces.perception_pipeline import ObjectPerceptionPipeline
from irobot.interfaces.plan_guards import build_formats, grounding_check, is_pure_stop
from irobot.interfaces.text_normalizer import preprocess

RATE = 16000
MODEL_PATH = os.path.expanduser("~/models/vosk-model-small-fr-0.22")
LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
# Valeurs lues au démarrage (informatif) ; chaque appel relit l'environnement via load_llm_settings().
_LLM_SETTINGS_AT_IMPORT = load_llm_settings()
LLM_MODEL = _LLM_SETTINGS_AT_IMPORT.model
LLM_CONNECT_TIMEOUT_SECONDS = _LLM_SETTINGS_AT_IMPORT.connect_timeout_seconds
LLM_READ_TIMEOUT_SECONDS = _LLM_SETTINGS_AT_IMPORT.read_timeout_seconds
LLM_HTTP_TIMEOUT = (LLM_CONNECT_TIMEOUT_SECONDS, LLM_READ_TIMEOUT_SECONDS)
LLM_WARMUP_READ_TIMEOUT_SECONDS = 120.0
# Attente max du préchauffage en mode une seule commande (--once / --text), surchargeable par env.
LLM_WARMUP_WAIT_SECONDS = 60.0
# LLM_RESPONSE_FORMAT : schema (chaîne de repli 8b) | json_object | none.
LLM_RESPONSE_FORMAT_MODES = ("schema", "json_object", "none")
LLM_DEFAULT_CONFIDENCE = 0.8
RUNTIME_SETTINGS: RuntimeSettings = load_runtime_settings()
MAX_PLAN_STEPS = RUNTIME_SETTINGS.max_plan_steps
MAX_DISTANCE_CM = RUNTIME_SETTINGS.max_distance_cm
MAX_ANGLE_DEG = RUNTIME_SETTINGS.max_angle_deg
MAX_DURATION_SEC = RUNTIME_SETTINGS.max_duration_sec
# Prompts courts et statiques (préfixe identique à chaque appel -> cache de prompt de llama-server).
# L'entrée utilisateur est déjà normalisée par text_normalizer.preprocess.
SYSTEM_PROMPT = """Tu convertis une consigne vocale pour un robot en JSON strict, sans aucun texte autour.
Format : {"intent":"...","target":null,"parameters":{},"confidence":0.9}
Intents :
- move_forward, move_backward : parameters {"distance":cm} ou {"duration":secondes}
- turn_left, turn_right : parameters {"angle":degrés} ou {"duration":secondes}
- stop
- search_and_approach_object : target "red" ou "yellow", parameters {"stand_off_cm":cm}
- follow_object : target "red" ou "yellow", parameters {"stand_off_cm":cm,"duration_s":secondes}
- follow_red_ball : target "red_ball"
- avoid_obstacle, spin_360, return_to_start
- move_square : parameters {"side":cm}
Règles : une seule action. Les nombres sont déjà en chiffres, distances en centimètres, durées en secondes. Sans valeur donnée : avance/recule -> duration 1 ; tourne -> angle 90. jaune = "yellow", rouge = "red". Consigne impossible ou hors liste -> {"intent":"unknown","target":null,"parameters":{},"confidence":0}.
Exemple :
« avance de 50 centimètres » -> {"intent":"move_forward","target":null,"parameters":{"distance":50},"confidence":0.9}"""

SYSTEM_PROMPT_PLAN = """Tu convertis une consigne vocale pour un robot en JSON strict, sans aucun texte autour.
Format : {"steps":[{"intent":"...","target":null,"parameters":{}}]}
Intents :
- move_forward, move_backward : parameters {"distance":cm} ou {"duration":secondes}
- turn_left, turn_right : parameters {"angle":degrés} ou {"duration":secondes}
- stop
- search_and_approach_object : target "red" ou "yellow", parameters {"stand_off_cm":cm}
- follow_object : target "red" ou "yellow", parameters {"stand_off_cm":cm,"duration_s":secondes}
- follow_red_ball : target "red_ball"
- avoid_obstacle, spin_360, return_to_start
- move_square : parameters {"side":cm}
Règles : une étape par action, dans l'ordre. Les nombres sont déjà en chiffres, distances en centimètres, durées en secondes. Sans valeur donnée : avance/recule -> duration 1 ; tourne -> angle 90. jaune = "yellow", rouge = "red". Consigne impossible ou hors liste -> {"steps":[]}.
Exemples :
« cherche la balle jaune approche toi à 100 centimètres de la balle jaune puis suis la pendant 300 secondes » -> {"steps":[{"intent":"search_and_approach_object","target":"yellow","parameters":{"stand_off_cm":100}},{"intent":"follow_object","target":"yellow","parameters":{"stand_off_cm":100,"duration_s":300}}]}
« avance de 50 centimètres puis tourne à gauche de 45 degrés » -> {"steps":[{"intent":"move_forward","target":null,"parameters":{"distance":50}},{"intent":"turn_left","target":null,"parameters":{"angle":45}}]}
« avance » -> {"steps":[{"intent":"move_forward","target":null,"parameters":{"duration":1}}]}
« suis la balle rouge » -> {"steps":[{"intent":"follow_red_ball","target":"red_ball","parameters":{}}]}
« fais un salto arrière » -> {"steps":[]}"""


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


def _llm_payload(system_prompt: str, user_text: str, max_tokens: int, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "stream": False,
        "cache_prompt": True,
    }


class ResponseFormatChain:
    """`response_format` essayés dans l'ordre (None = sans) ; le premier accepté est mémorisé."""

    def __init__(self, formats: list[dict[str, Any] | None]):
        self.formats = list(formats)
        self._start = 0

    def candidates(self) -> list[tuple[int, dict[str, Any] | None]]:
        return list(enumerate(self.formats))[self._start:]

    def accept(self, index: int) -> None:
        self._start = index

    def reset(self) -> None:
        self._start = 0


# Plan : json_schema strict -> json_object + schema -> json_object -> sans (selon la version de llama-server).
PLAN_RESPONSE_FORMATS = ResponseFormatChain(build_formats(False, True))
INTENT_RESPONSE_FORMATS = ResponseFormatChain(build_formats(False, False))


def reset_response_format_cache() -> None:
    PLAN_RESPONSE_FORMATS.reset()
    INTENT_RESPONSE_FORMATS.reset()


def llm_response_format_mode(environ: Any = None) -> str:
    """Lit LLM_RESPONSE_FORMAT (schema | json_object | none) ; valeur absente ou inconnue -> schema."""
    env = os.environ if environ is None else environ
    mode = (env.get("LLM_RESPONSE_FORMAT") or "").strip().lower()
    return mode if mode in LLM_RESPONSE_FORMAT_MODES else "schema"


def _select_formats(schema_chain: ResponseFormatChain) -> ResponseFormatChain:
    mode = llm_response_format_mode()
    if mode == "json_object":
        return ResponseFormatChain([{"type": "json_object"}])
    if mode == "none":
        return ResponseFormatChain([None])
    return schema_chain


def _response_format_kind(fmt: dict[str, Any] | None) -> str:
    """json_schema | json_object_schema | json_object | none."""
    if fmt is None:
        return "none"
    kind = str(fmt.get("type"))
    if kind == "json_object" and "schema" in fmt:
        return "json_object_schema"
    return kind


def llm_warmup_wait_seconds(environ: Any = None) -> float:
    """Lit LLM_WARMUP_WAIT_SECONDS (>= 0) ; valeur absente ou invalide -> 60 s."""
    env = os.environ if environ is None else environ
    try:
        value = float(env["LLM_WARMUP_WAIT_SECONDS"])
    except (KeyError, TypeError, ValueError):
        return LLM_WARMUP_WAIT_SECONDS
    return value if math.isfinite(value) and value >= 0 else LLM_WARMUP_WAIT_SECONDS


def _post_llm_chat(
    payload: dict[str, Any],
    timeout: tuple[float, float],
    formats: ResponseFormatChain,
    meta: dict[str, Any] | None = None,
) -> str:
    """Appel non streamé ; format suivant sur HTTP 400 ; retourne le contenu texte de la réponse.

    `meta` (optionnel) reçoit la durée réelle, le nombre de requêtes, le format utilisé et
    `usage`/`timings` de llama-server, y compris quand l'appel échoue.
    """
    meta = {} if meta is None else meta
    meta.update(
        llm_latency_seconds=None,
        llm_response_format=None,
        llm_attempts=0,
        llm_prompt_tokens=None,
        llm_completion_tokens=None,
        llm_timings=None,
    )
    started = time.monotonic()
    try:
        candidates = formats.candidates()
        response = None
        index = 0
        for position, (index, fmt) in enumerate(candidates):
            body = dict(payload)
            if fmt is not None:
                body["response_format"] = fmt
            meta["llm_attempts"] += 1
            meta["llm_response_format"] = _response_format_kind(fmt)
            response = requests.post(LLM_URL, json=body, timeout=timeout)
            if getattr(response, "status_code", 200) == 400 and position < len(candidates) - 1:
                continue
            break
        response.raise_for_status()
        formats.accept(index)
        data = response.json()
        usage = data.get("usage") if isinstance(data, dict) else None
        if isinstance(usage, dict):
            meta["llm_prompt_tokens"] = usage.get("prompt_tokens")
            meta["llm_completion_tokens"] = usage.get("completion_tokens")
        timings = data.get("timings") if isinstance(data, dict) else None
        if isinstance(timings, dict):
            meta["llm_timings"] = dict(timings)
        return str(data["choices"][0]["message"]["content"]).strip()
    finally:
        meta["llm_latency_seconds"] = round(time.monotonic() - started, 3)


def _llm_error_reason(exc: Exception, read_timeout: float) -> str:
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "serveur LLM injoignable"
    if isinstance(exc, requests.exceptions.Timeout):
        return f"LLM trop lent (> {read_timeout:g}s)"
    if isinstance(exc, requests.exceptions.HTTPError):
        return f"erreur HTTP du serveur LLM ({exc})"
    return f"erreur LLM ({type(exc).__name__}: {exc})"


def _llm_confidence(value: Any) -> float:
    if value is None or isinstance(value, bool):
        return LLM_DEFAULT_CONFIDENCE
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return LLM_DEFAULT_CONFIDENCE
    if not math.isfinite(confidence):
        return LLM_DEFAULT_CONFIDENCE
    return max(0.0, min(1.0, confidence))


def _intent_from_llm_step(step: Any, raw_text: str) -> Intent | None:
    """Reconstruit un Intent depuis un objet JSON du LLM ; None si l'objet est malformé."""
    if not isinstance(step, dict):
        return None
    parameters = step.get("parameters")
    if parameters is None:
        parameters = {}
    if not isinstance(parameters, dict):
        return None
    target = step.get("target")
    return Intent(
        name=str(step.get("intent") or step.get("name") or "unknown").strip(),
        target=str(target) if target is not None else None,
        parameters=dict(parameters),
        confidence=_llm_confidence(step.get("confidence")),
        raw_text=raw_text,
    )


def ask_llm_for_intent(text: str) -> Intent:
    """Demande un JSON de type Intent au LLM local, puis reconstruit l'objet Intent."""
    settings = load_llm_settings()
    payload = _llm_payload(SYSTEM_PROMPT, preprocess(text), settings.max_tokens_intent, settings.model)
    try:
        content = _post_llm_chat(
            payload,
            (settings.connect_timeout_seconds, settings.read_timeout_seconds),
            _select_formats(INTENT_RESPONSE_FORMATS),
        )
        parsed = _parse_llm_json_payload(content)
        intent = _intent_from_llm_step(parsed, text) if parsed else None
        return intent if intent is not None else IntentParser().parse(text)
    except Exception:
        return IntentParser().parse(text)


def _normalize_llm_step(step: Any) -> dict[str, Any] | None:
    """Étape LLM tolérante (target absent -> None, parameters absent -> {}) ; None si malformée."""
    if not isinstance(step, dict):
        return None
    parameters = step.get("parameters")
    if parameters is None:
        parameters = {}
    if not isinstance(parameters, dict):
        return None
    name = str(step.get("intent") or step.get("name") or "unknown").strip().lower()
    return {
        **step,
        "intent": PLAN_INTENT_SYNONYMS.get(name, name),
        "target": step.get("target"),
        "parameters": dict(parameters),
    }


def ask_llm_for_intent_plan_with_trace(text: str) -> tuple[list[Intent], dict[str, Any]]:
    """Demande au LLM un plan ordonné d'intentions et retourne des métadonnées de trace.

    - JSON valide avec `steps: []` -> ([], source "llm_unsupported") : commande hors périmètre ;
    - plan non justifié par la phrase prétraitée (`grounding_check`) -> ([], source "llm_ungrounded") ;
    - timeout, erreur HTTP, JSON invalide, `steps` absent/non liste ou aucune étape exploitable
      -> repli sur IntentParser (texte d'origine).
    """
    normalized_text = preprocess(text)
    settings = load_llm_settings()
    payload = _llm_payload(SYSTEM_PROMPT_PLAN, normalized_text, settings.max_tokens_plan, settings.model)
    meta: dict[str, Any] = {}

    def _fallback(console_reason: str, **trace: Any) -> tuple[list[Intent], dict[str, Any]]:
        print(f"[LLM] {console_reason}, repli sur le parseur local", flush=True)
        return IntentParser().parse_plan(text), {
            "source": "local_parser_fast_fallback",
            "llm_content": None,
            "llm_json": None,
            "normalized_text": normalized_text,
            **meta,
            **trace,
        }

    try:
        content = _post_llm_chat(
            payload,
            (settings.connect_timeout_seconds, settings.read_timeout_seconds),
            _select_formats(PLAN_RESPONSE_FORMATS),
            meta,
        )
    except Exception as exc:
        return _fallback(
            _llm_error_reason(exc, settings.read_timeout_seconds),
            error=f"{type(exc).__name__}: {exc}",
            error_type=type(exc).__name__,
        )

    parsed = _parse_llm_json_payload(content)
    if not parsed:
        return _fallback("JSON invalide", llm_content=content, reason="invalid json")

    raw_steps = parsed.get("steps")
    if not isinstance(raw_steps, list):
        return _fallback("réponse sans « steps »", llm_content=content, llm_json=parsed, reason="missing steps")

    trace: dict[str, Any] = {"llm_content": content, "llm_json": parsed, "normalized_text": normalized_text, **meta}
    if not raw_steps:
        return [], {"source": "llm_unsupported", **trace}

    steps: list[dict[str, Any]] = []
    skipped: list[int] = []
    for index, step in enumerate(raw_steps):
        normalized_step = _normalize_llm_step(step)
        if normalized_step is None:
            skipped.append(index)
            continue
        steps.append(normalized_step)

    if not steps:
        return _fallback(
            "aucune étape exploitable", llm_content=content, llm_json=parsed, reason="no usable step",
            skipped_steps=skipped,
        )

    # Le LLM propose, le lexique dispose : contrôle sur le texte réellement envoyé au LLM.
    kept, guard_reason, guard_notes = grounding_check(normalized_text, steps)
    trace["guard_notes"] = guard_notes
    trace["skipped_steps"] = skipped
    if guard_reason or not kept:
        return [], {"source": "llm_ungrounded", **trace, "guard_reason": guard_reason or "no grounded step"}

    intents = [intent for step in kept if (intent := _intent_from_llm_step(step, text)) is not None]
    return intents, {"source": "llm_plan", **trace}


def warm_up_llm(timeout: tuple[float, float] | None = None) -> bool:
    """Requête minimale avec le prompt système du plan pour remplir le cache de prompt du serveur."""
    settings = load_llm_settings()
    payload = _llm_payload(SYSTEM_PROMPT_PLAN, "stop", 1, settings.model)
    try:
        _post_llm_chat(
            payload,
            timeout or (settings.connect_timeout_seconds, LLM_WARMUP_READ_TIMEOUT_SECONDS),
            _select_formats(PLAN_RESPONSE_FORMATS),
        )
        return True
    except Exception:
        return False


class LLMWarmup:
    """Préchauffage en thread daemon ; `wait()` le rend bloquant (mode une seule commande).

    Statuts : skipped (non lancé) | running | done | failed | timeout (attente expirée, définitif).
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._result: bool | None = None
        self._timed_out = False

    def start(self) -> "LLMWarmup":
        self._thread = threading.Thread(target=self._run, name="llm-warmup", daemon=True)
        self._thread.start()
        return self

    def _run(self) -> None:
        self._result = warm_up_llm()

    def wait(self, timeout: float) -> str:
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout)
            if self._thread.is_alive():
                self._timed_out = True
        return self.status

    @property
    def status(self) -> str:
        if self._thread is None:
            return "skipped"
        if self._timed_out:
            return "timeout"
        if self._thread.is_alive():
            return "running"
        return "done" if self._result else "failed"


def warm_up_llm_async() -> threading.Thread:
    """Lance le préchauffage en arrière-plan (thread daemon) sans bloquer le démarrage."""
    thread = threading.Thread(target=warm_up_llm, name="llm-warmup", daemon=True)
    thread.start()
    return thread


def ask_llm_for_intent_plan(text: str) -> list[Intent]:
    """Compatibilité : retourne uniquement la liste d'intents planifiées."""
    intents, _ = ask_llm_for_intent_plan_with_trace(text)
    return intents


DEFAULT_MOVE_DURATION_SEC = 1.0
DEFAULT_TURN_ANGLE_DEG = 90.0
PLAN_INTENT_SYNONYMS = {
    "contourner_obstacle": "contour_obstacle",
    "contourne_obstacle": "contour_obstacle",
    "avoid": "avoid_obstacle",
    "find_object": "search_and_approach_object",
    "search_object": "search_and_approach_object",
    "detect_object": "search_and_approach_object",
    "approach_object": "search_and_approach_object",
    "follow": "follow_object",
    "track": "follow_object",
    "track_object": "follow_object",
    "follow_target": "follow_object",
    "suivre": "follow_object",
    "suit": "follow_object",
    "rotate_360": "spin_360",
    "spin": "spin_360",
    "square": "move_square",
    "path": "execute_path",
    "trajectory": "execute_path",
    "trajet": "execute_path",
    "go_home": "return_to_start",
    "back_to_start": "return_to_start",
}
# Sources de plan rejetées sans repli parseur ni mouvement.
UNSUPPORTED_PLAN_SOURCES = {"llm_unsupported", "llm_ungrounded"}
OBJECT_INTENTS = {"search_and_approach_object", "follow_object"}
TARGET_COLOR_SYNONYMS = {
    "jaune": "yellow",
    "yellow": "yellow",
    "balle jaune": "yellow",
    "yellow_ball": "yellow",
    "rouge": "red",
    "red": "red",
    "balle rouge": "red",
    "red_ball": "red",
}
DEFAULT_STAND_OFF_CM = 100.0
DEFAULT_FOLLOW_DURATION_SEC = 60.0
MIN_OBJECT_DURATION_SEC = 1.0
MIN_SEARCH_TIMEOUT_SEC = 1.0
MAX_SEARCH_TIMEOUT_SEC = 120.0


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
            elif intent.name in OBJECT_INTENTS:
                intent = self._sanitize_object_intent(intent)
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

    def _effective_step_timeout(self, intent: Intent) -> float:
        base = float(self.settings.step_timeout_seconds)
        params = intent.parameters or {}
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
        synonyms = PLAN_INTENT_SYNONYMS
        normalized: list[Intent] = []
        for intent in intents:
            name = intent.name.strip().lower()
            mapped = synonyms.get(name, name)
            target = intent.target
            parameters = dict(intent.parameters)
            if mapped in OBJECT_INTENTS:
                target, parameters = self._normalize_object_target(mapped, target, parameters)
            normalized.append(
                Intent(
                    name=mapped,
                    target=target,
                    parameters=parameters,
                    confidence=intent.confidence,
                    raw_text=intent.raw_text,
                )
            )
        return normalized

    @staticmethod
    def _color_from_label(value: Any) -> str | None:
        if value is None:
            return None
        return TARGET_COLOR_SYNONYMS.get(str(value).strip().lower())

    def _normalize_object_target(
        self, name: str, target: str | None, parameters: dict[str, Any]
    ) -> tuple[str | None, dict[str, Any]]:
        """Ramène les couleurs de cible (jaune, balle rouge...) à `yellow`/`red`."""
        color = self._color_from_label(target)
        if color is None:
            color = self._color_from_label(parameters.get("target_object"))
        if color is not None:
            target = color
            parameters["target_object"] = color
        elif target is None and parameters.get("target_object") is not None and name == "follow_object":
            target = str(parameters["target_object"])
        return target, parameters

    def _to_float(self, value: Any, default: float | None = None) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default

    def _sanitize_object_intent(self, intent: Intent) -> Intent:
        """Borne les paramètres de recherche/approche/suivi ; valeurs invalides -> défauts."""
        params = dict(intent.parameters)
        settings = self.settings

        if "stand_off_cm" in params:
            value = self._to_float(params["stand_off_cm"], DEFAULT_STAND_OFF_CM)
            params["stand_off_cm"] = max(
                float(settings.min_stand_off_cm), min(value, float(settings.max_stand_off_cm))
            )
        if "duration_s" in params:
            value = self._to_float(params["duration_s"], DEFAULT_FOLLOW_DURATION_SEC)
            params["duration_s"] = max(MIN_OBJECT_DURATION_SEC, min(value, float(settings.max_follow_duration_sec)))
        if "search_timeout_s" in params:
            value = self._to_float(params["search_timeout_s"], float(settings.search_timeout_seconds))
            params["search_timeout_s"] = max(MIN_SEARCH_TIMEOUT_SEC, min(value, MAX_SEARCH_TIMEOUT_SEC))

        return Intent(
            name=intent.name,
            target=intent.target,
            parameters=params,
            confidence=intent.confidence,
            raw_text=intent.raw_text,
        )

    def _sanitize_primitive_intent(self, intent: Intent) -> Intent:
        """Normalise et borne les paramètres de primitives pour un plan sûr."""
        params = dict(intent.parameters)
        if intent.name in {"move_forward", "move_backward"}:
            distance = self._to_float(params.get("distance"), None)
            unit = normalize_distance_unit(params.get("unit"))
            duration = self._to_float(params.get("duration"), None)

            if distance is None and duration is None:
                duration = DEFAULT_MOVE_DURATION_SEC

            if distance is not None:
                if unit == "m":
                    distance = max(0.01, min(distance, self.settings.max_distance_cm / 100.0))
                else:
                    distance = max(0.1, min(distance, self.settings.max_distance_cm))
                params["distance"] = distance
                params["unit"] = unit

            if duration is not None:
                params["duration"] = max(0.1, min(duration, self.settings.max_duration_sec))

        if intent.name in {"turn_left", "turn_right"}:
            angle = self._to_float(params.get("angle"), None)
            duration = self._to_float(params.get("duration"), None)
            if angle is None and duration is None and not params.get("full_rotation"):
                angle = DEFAULT_TURN_ANGLE_DEG
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

    def _safe_stop(self) -> None:
        stop = getattr(self.robot, "stop", None)
        if not callable(stop):
            return
        try:
            stop()
        except Exception:
            pass

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

        warmup_status = self.warmup.status if self.warmup is not None else "skipped"
        if is_pure_stop(text):
            # Sécurité : arrêt pur traité localement, sans LLM ni normalisation des nombres.
            intents = [Intent(name="stop", raw_text=text, confidence=1.0)]
            plan_trace = {"source": "local_stop", "llm_content": None, "llm_json": None, "normalized_text": None}
        elif self.use_llm:
            warmup_status = self._await_warmup()
            intents, plan_trace = ask_llm_for_intent_plan_with_trace(text)
        else:
            intents = self.parser.parse_plan(text)
            plan_trace = {
                "source": "local_parser",
                "llm_content": None,
                "llm_json": None,
                "normalized_text": preprocess(text),
            }

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

        if plan_trace.get("source") in UNSUPPORTED_PLAN_SOURCES:
            # Hors périmètre ({"steps": []}) ou plan non justifié par la phrase : rejet sans repli ni mouvement.
            self.mission.fail("unsupported command")
            self._write_trace_event(
                trace_path,
                {
                    "event": "plan_unsupported",
                    "text": text,
                    "normalized_text": plan_trace.get("normalized_text"),
                    "llm_content": plan_trace.get("llm_content"),
                    "guard_reason": plan_trace.get("guard_reason"),
                    "guard_notes": plan_trace.get("guard_notes"),
                },
            )
            return {
                "input": text,
                "status": "rejected",
                "reason": "unsupported command",
                "guard_reason": plan_trace.get("guard_reason"),
                "steps": [],
                "trace_path": str(trace_path),
                "source": plan_trace.get("source"),
                "mission": self.mission.as_dict(),
            }

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

        if validation_errors:
            self.mission.fail("invalid plan step")
            return {
                "input": text,
                "status": "rejected",
                "reason": "invalid plan step",
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
            self._clear_emergency_stop()
            result = self.handle_text_as_plan(text)
            print(f"[RUNTIME] {result}", flush=True)
            return result
        return {"status": "no_transcript"}

    def _call_robot(self, method: str) -> None:
        func = getattr(self.robot, method, None)
        if callable(func):
            try:
                func()
            except Exception:
                pass

    def _clear_emergency_stop(self) -> None:
        self._call_robot("clear_emergency_stop")

    def _request_emergency_stop(self) -> None:
        if callable(getattr(self.robot, "request_emergency_stop", None)):
            self._call_robot("request_emergency_stop")
        else:
            self._safe_stop()

    def mission_running(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def _is_stop_phrase(self, text: str) -> bool:
        return is_pure_stop(text) or self.parser.parse(text).name == "stop"

    def _mission_worker(self, text: str) -> None:
        try:
            self.last_result = self.handle_text_as_plan(text)
            print(f"[RUNTIME] {self.last_result}", flush=True)
        except Exception as exc:
            self.last_result = {"status": "failed", "error": str(exc)}
            print(f"[RUNTIME] erreur mission : {exc}", flush=True)
            self._safe_stop()

    def handle_transcript(self, text: str):
        """Stop immédiat pendant une mission, sinon démarre une nouvelle mission."""
        if self.mission_running():
            if self._is_stop_phrase(text):
                print("[RUNTIME] Arrêt d'urgence demandé.", flush=True)
                self._request_emergency_stop()
            else:
                print("[RUNTIME] Mission en cours : phrase ignorée (dis « stop » pour arrêter).", flush=True)
            return None

        # Effacé ici (thread principal) et non dans le worker pour ne pas écraser un stop tardif.
        self._clear_emergency_stop()
        if not self.threaded:
            self.last_result = self.handle_text_as_plan(text)
            print(f"[RUNTIME] {self.last_result}", flush=True)
            return self.last_result
        self._worker = threading.Thread(target=self._mission_worker, args=(text,), name="mission-worker", daemon=True)
        self._worker.start()
        return None

    def listen_forever(self):
        device = resolve_input_device(self.input_device)
        try:
            for text in transcribe_loop(device):
                print(f"\n[VOIX] {text}", flush=True)
                self.handle_transcript(text)
        except KeyboardInterrupt:
            print("\nInterruption clavier : arrêt du runtime vocal.")
            self._abort_mission()

    def _abort_mission(self) -> None:
        self._request_emergency_stop()
        worker = self._worker
        if worker is not None and worker.is_alive() and worker is not threading.current_thread():
            worker.join(timeout=2.0)
        self._safe_stop()

    def close(self) -> None:
        """Arrête proprement les périphériques matériels et les threads d'arrière-plan"""
        self._abort_mission()
        if self.perception is not None and hasattr(self.perception, "close"):
            try:
                self.perception.close()
            except Exception:
                pass
        if self.robot is not None and hasattr(self.robot, "stop"):
            try:
                self.robot.stop()
            except Exception:
                pass

def build_hardware_runtime() -> dict[str, Any]:
    """Construit les dépendances hardware réelles quand elles sont disponibles (Linux/Pi)."""
    runtime: dict[str, Any] = {
        "robot": None,
        "camera": None,
        "sensor": None,
        "perception": None,
    }

    if not sys.platform.startswith("linux"):
        return runtime

    try:
        from irobot.hardware.smart_car.smart_car import SmartCar2WD
        from irobot.interfaces.robot_controller import RobotController

        car = SmartCar2WD(require_obstacle_sensor=False)
        car.set_speed(0.5)
        runtime["robot"] = RobotController(car)
        runtime["sensor"] = car.distance_sensor
    except Exception:
        runtime["robot"] = None
        runtime["sensor"] = None

    try:
        from irobot.hardware.camera.camera_live_pipeline import CameraLivePerceptionPipeline

        robot = runtime["robot"]
        distance_reader = robot.read_distance_cm if robot is not None and runtime["sensor"] is not None else None
        perception = CameraLivePerceptionPipeline(distance_reader=distance_reader)
        runtime["camera"] = perception
        runtime["perception"] = perception
    except Exception:
        runtime["camera"] = None
        runtime["perception"] = None

    return runtime

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
    parser.add_argument(
        "--text",
        default=None,
        help="Traite cette phrase (sans micro) puis s'arrête.",
    )
    args = parser.parse_args()

    runtime = None
    try:
        warmup = LLMWarmup().start() if not args.no_llm else None
        hardware = build_hardware_runtime()
        runtime = VoiceRuntime(
            robot=hardware["robot"],
            camera=hardware["camera"],
            sensor=hardware["sensor"],
            perception=hardware["perception"],
            input_device=args.input_device,
            use_llm=not args.no_llm,
        )
        runtime.warmup = warmup
        # Une seule commande : la vraie requête attend le préchauffage ; écoute continue : arrière-plan.
        runtime.wait_for_warmup = bool(args.once or args.text)
        if args.text:
            runtime._clear_emergency_stop()
            result = runtime.handle_text_as_plan(args.text)
            print(f"[RUNTIME] {result}", flush=True)
            return
        if args.once:
            runtime.listen_once()
            return
        runtime.listen_forever()
    except RuntimeError as exc:
        print(f"Erreur : {exc}")
        sys.exit(1)
    finally:
        if runtime is not None:
            runtime.close()

if __name__ == "__main__":
    main()
