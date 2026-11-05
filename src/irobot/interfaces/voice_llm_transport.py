"""HTTP transport, response formats and static prompts for the local LLM."""

from __future__ import annotations

import json
import math
import os
import time
from collections.abc import Mapping
from typing import Any, Protocol

import requests

from irobot.interfaces.plan_guards import build_formats

LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
LLM_WARMUP_READ_TIMEOUT_SECONDS = 120.0
# Attente max du préchauffage en mode une seule commande (--once / --text), surchargeable par env.
LLM_WARMUP_WAIT_SECONDS = 60.0
# LLM_RESPONSE_FORMAT : schema (chaîne de repli 8b) | json_object | none.
LLM_RESPONSE_FORMAT_MODES = ("schema", "json_object", "none")
LLM_DEFAULT_CONFIDENCE = 0.8
# Prompt court et statique (préfixe identique à chaque appel -> cache de prompt de llama-server).
# L'entrée utilisateur est déjà normalisée par text_normalizer.preprocess.
SYSTEM_PROMPT_PLAN = """Tu convertis une consigne vocale pour un robot en JSON strict, sans aucun texte autour.
Format : {"steps":[{"intent":"...","target":null,"parameters":{}}]}
Intents :
- move_forward, move_backward : parameters {"distance":cm} ou {"duration":secondes}
- turn_left, turn_right : parameters {"angle":degrés} ou {"duration":secondes}
- stop
- search_and_approach_object : target "red", "yellow", "ball", "marker" (tag) ou "face" (personne, humain, visage, moi), parameters {"stand_off_cm":cm}
- follow_object : target "red" ou "yellow", parameters {"stand_off_cm":cm,"duration_s":secondes}
- follow_red_ball : target "red_ball"
- follow_person : target "face", pour « suis-moi » ou « suis un humain »
- avoid_obstacle, spin_360, return_to_start
- move_square : parameters {"side":cm}
Règles : une étape par action, dans l'ordre. Les nombres sont déjà en chiffres, distances en centimètres, durées en secondes. Sans valeur donnée : avance/recule -> duration 1 ; tourne -> angle 90. jaune = "yellow", rouge = "red". Consigne impossible ou hors liste -> {"steps":[]}.
« moi », « humain », « personne », « visage » désignent la personne : target "face", jamais une couleur ni "marker". « tag » et « marker » désignent le marqueur ArUco : target "marker". Pour rejoindre ou approcher la personne, utilise search_and_approach_object. N'invente pas de distance.
Exemples :
« approche toi de moi » -> {"steps":[{"intent":"search_and_approach_object","target":"face","parameters":{}}]}
« rapproche toi à 100 centimètres de moi puis tourne à gauche » -> {"steps":[{"intent":"search_and_approach_object","target":"face","parameters":{"stand_off_cm":100}},{"intent":"turn_left","target":null,"parameters":{"angle":90}}]}
« suis-moi » -> {"steps":[{"intent":"follow_person","target":"face","parameters":{}}]}
« cherche la balle jaune approche toi à 100 centimètres de la balle jaune puis suis la pendant 300 secondes » -> {"steps":[{"intent":"search_and_approach_object","target":"yellow","parameters":{"stand_off_cm":100}},{"intent":"follow_object","target":"yellow","parameters":{"stand_off_cm":100,"duration_s":300}}]}
« avance de 50 centimètres puis tourne à gauche de 45 degrés » -> {"steps":[{"intent":"move_forward","target":null,"parameters":{"distance":50}},{"intent":"turn_left","target":null,"parameters":{"angle":45}}]}
« avance » -> {"steps":[{"intent":"move_forward","target":null,"parameters":{"duration":1}}]}
« suis la balle rouge » -> {"steps":[{"intent":"follow_red_ball","target":"red_ball","parameters":{}}]}
« cherche la balle » -> {"steps":[{"intent":"search_and_approach_object","target":"ball","parameters":{}}]}
« trouve le tag » -> {"steps":[{"intent":"search_and_approach_object","target":"marker","parameters":{}}]}
« fais un salto arrière » -> {"steps":[]}"""


def parse_llm_json_payload(content: str) -> dict[str, Any] | None:
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


def llm_payload(system_prompt: str, user_text: str, max_tokens: int, model: str) -> dict[str, Any]:
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


PLAN_RESPONSE_FORMATS = ResponseFormatChain(build_formats(False, True))


class LLMPost(Protocol):
    """Typed transport seam shared by the compatibility facade and interpreter."""

    def __call__(
        self, payload: dict[str, Any], timeout: tuple[float, float],
        formats: ResponseFormatChain, meta: dict[str, Any] | None = None,
    ) -> str: ...


def llm_response_format_mode(environ: Mapping[str, str] | None = None) -> str:
    """Lit LLM_RESPONSE_FORMAT (schema | json_object | none) ; valeur absente ou inconnue -> schema."""
    env = os.environ if environ is None else environ
    mode = (env.get("LLM_RESPONSE_FORMAT") or "").strip().lower()
    return mode if mode in LLM_RESPONSE_FORMAT_MODES else "schema"


def select_formats(schema_chain: ResponseFormatChain) -> ResponseFormatChain:
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


def llm_warmup_wait_seconds(environ: Mapping[str, str] | None = None) -> float:
    """Lit LLM_WARMUP_WAIT_SECONDS (>= 0) ; valeur absente ou invalide -> 60 s."""
    env = os.environ if environ is None else environ
    try:
        value = float(env["LLM_WARMUP_WAIT_SECONDS"])
    except (KeyError, TypeError, ValueError):
        return LLM_WARMUP_WAIT_SECONDS
    return value if math.isfinite(value) and value >= 0 else LLM_WARMUP_WAIT_SECONDS


def post_llm_chat(
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
        if response is None:
            raise RuntimeError("Aucun format de réponse LLM disponible")
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


def llm_error_reason(exc: Exception, read_timeout: float) -> str:
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "serveur LLM injoignable"
    if isinstance(exc, requests.exceptions.Timeout):
        return f"LLM trop lent (> {read_timeout:g}s)"
    if isinstance(exc, requests.exceptions.HTTPError):
        return f"erreur HTTP du serveur LLM ({exc})"
    return f"erreur LLM ({type(exc).__name__}: {exc})"
