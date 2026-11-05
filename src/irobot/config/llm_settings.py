"""Settings for the local LLM client."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMSettings:
    """Local llama-server settings, overridable through environment variables."""

    model: str = "qwen2.5-1.5b"
    connect_timeout_seconds: float = 1.0
    read_timeout_seconds: float = 10.0
    max_tokens_plan: int = 120


def _env_positive(environ: Mapping[str, str], key: str, default: float, cast=float):
    try:
        value = cast(environ[key])
    except (KeyError, TypeError, ValueError):
        return default
    return value if value > 0 else default


def load_llm_settings(environ: Mapping[str, str] | None = None) -> LLMSettings:
    """Read LLM_* variables; missing or invalid values use defaults."""
    env = os.environ if environ is None else environ
    defaults = LLMSettings()
    return LLMSettings(
        model=(env.get("LLM_MODEL") or "").strip() or defaults.model,
        connect_timeout_seconds=_env_positive(env, "LLM_CONNECT_TIMEOUT_SECONDS", defaults.connect_timeout_seconds),
        read_timeout_seconds=_env_positive(env, "LLM_READ_TIMEOUT_SECONDS", defaults.read_timeout_seconds),
        max_tokens_plan=_env_positive(env, "LLM_MAX_TOKENS_PLAN", defaults.max_tokens_plan, int),
    )
