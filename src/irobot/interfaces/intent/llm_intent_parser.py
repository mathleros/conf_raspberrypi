"""Language-only LLM interpretation and deterministic refusal/fallback."""

from __future__ import annotations

import math
import threading
from collections.abc import Callable
from typing import Any

from irobot.config.llm_settings import load_llm_settings
from irobot.domain.intent import Intent
from irobot.interfaces.intent.text_intent_parser import TextIntentParser
from irobot.interfaces.plan_guards import (
    contains_unsupported_follow_step,
    follow_request_refusal,
    grounding_check,
)
from irobot.interfaces.text_normalizer import preprocess
from irobot.interfaces.voice_constants import PLAN_INTENT_SYNONYMS
from irobot.interfaces.voice_llm_transport import (
    LLM_DEFAULT_CONFIDENCE,
    LLM_WARMUP_READ_TIMEOUT_SECONDS,
    PLAN_RESPONSE_FORMATS,
    SYSTEM_PROMPT_PLAN,
    LLMPost,
    llm_error_reason,
    llm_payload,
    parse_llm_json_payload,
    post_llm_chat,
    select_formats,
)

LLMPlanParser = Callable[[str], tuple[list[Intent], dict[str, Any]]]


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


def _step_parameters(step: Any) -> dict[str, Any] | None:
    """Copie des `parameters` d'une étape LLM (absent -> {}) ; None si l'étape ou `parameters` est malformé."""
    if not isinstance(step, dict):
        return None
    parameters = step.get("parameters")
    if parameters is None:
        return {}
    if not isinstance(parameters, dict):
        return None
    return dict(parameters)


def _intent_from_llm_step(step: Any, raw_text: str) -> Intent | None:
    """Reconstruit un Intent depuis un objet JSON du LLM ; None si l'objet est malformé."""
    parameters = _step_parameters(step)
    if parameters is None:
        return None
    target = step.get("target")
    return Intent(
        name=str(step.get("intent") or step.get("name") or "unknown").strip(),
        target=str(target) if target is not None else None,
        parameters=parameters,
        confidence=_llm_confidence(step.get("confidence")),
        raw_text=raw_text,
    )


def _normalize_llm_step(step: Any) -> dict[str, Any] | None:
    """Étape LLM tolérante (target absent -> None, parameters absent -> {}) ; None si malformée."""
    parameters = _step_parameters(step)
    if parameters is None:
        return None
    name = str(step.get("intent") or step.get("name") or "unknown").strip().lower()
    return {
        **step,
        "intent": PLAN_INTENT_SYNONYMS.get(name, name),
        "target": step.get("target"),
        "parameters": parameters,
    }


def _fallback_plan(
    text: str, normalized_text: str, meta: dict[str, Any], console_reason: str, **trace: Any,
) -> tuple[list[Intent], dict[str, Any]]:
    print(f"[LLM] {console_reason}, repli sur le parseur local", flush=True)
    return TextIntentParser().parse_plan(text), {
        "source": "local_parser_fast_fallback",
        "llm_content": None,
        "llm_json": None,
        "normalized_text": normalized_text,
        **meta,
        **trace,
    }


def ask_llm_for_intent_plan_with_trace(
    text: str, *, post: LLMPost = post_llm_chat,
) -> tuple[list[Intent], dict[str, Any]]:
    """Demande au LLM un plan ordonné d'intentions et retourne des métadonnées de trace.

    - JSON valide avec `steps: []` -> ([], source "llm_unsupported") : commande hors périmètre ;
    - plan non justifié par la phrase prétraitée (`grounding_check`) -> ([], source "llm_ungrounded") ;
    - timeout, erreur HTTP, JSON invalide, `steps` absent/non liste ou aucune étape exploitable
      -> repli sur TextIntentParser (texte d'origine).
    """
    refusal = follow_request_refusal(text)
    if refusal:
        return [], {"source": "llm_follow_refused", "guard_reason": refusal}
    normalized_text = preprocess(text)
    settings = load_llm_settings()
    payload = llm_payload(SYSTEM_PROMPT_PLAN, normalized_text, settings.max_tokens_plan, settings.model)
    meta: dict[str, Any] = {}

    try:
        content = post(
            payload,
            (settings.connect_timeout_seconds, settings.read_timeout_seconds),
            select_formats(PLAN_RESPONSE_FORMATS),
            meta,
        )
    except Exception as exc:
        return _fallback_plan(
            text, normalized_text, meta,
            llm_error_reason(exc, settings.read_timeout_seconds),
            error=f"{type(exc).__name__}: {exc}",
            error_type=type(exc).__name__,
        )

    return _interpret_plan_response(text, normalized_text, content, meta)


def _interpret_plan_response(
    text: str, normalized_text: str, content: str, meta: dict[str, Any],
) -> tuple[list[Intent], dict[str, Any]]:
    parsed = parse_llm_json_payload(content)
    if not parsed:
        return _fallback_plan(text, normalized_text, meta, "JSON invalide", llm_content=content, reason="invalid json")
    if contains_unsupported_follow_step(parsed):
        return [], {"source": "llm_follow_refused", "guard_reason": "unsupported_follow_target"}

    raw_steps = parsed.get("steps")
    if not isinstance(raw_steps, list):
        return _fallback_plan(
            text, normalized_text, meta, "réponse sans « steps »",
            llm_content=content, llm_json=parsed, reason="missing steps",
        )

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
        return _fallback_plan(
            text, normalized_text, meta, "aucune étape exploitable",
            llm_content=content, llm_json=parsed, reason="no usable step", skipped_steps=skipped,
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
    payload = llm_payload(SYSTEM_PROMPT_PLAN, "stop", 1, settings.model)
    try:
        post_llm_chat(
            payload,
            timeout or (settings.connect_timeout_seconds, LLM_WARMUP_READ_TIMEOUT_SECONDS),
            select_formats(PLAN_RESPONSE_FORMATS),
        )
        return True
    except Exception as exc:
        print(f"[LLM] Echec du prechauffage : {exc}", flush=True)
        return False


class LLMWarmup:
    """Préchauffage en thread daemon ; `wait()` le rend bloquant (mode une seule commande).

    Statuts : skipped (non lancé) | running | done | failed | timeout (attente expirée, définitif).
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._result: bool | None = None
        self._timed_out = False

    def start(self) -> LLMWarmup:
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
