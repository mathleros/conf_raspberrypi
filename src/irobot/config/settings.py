"""Global project settings and runtime calibration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import tomllib

DEFAULT_SPEED = 0.5
DEFAULT_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class MarkerIdentity:
    family: str
    dictionary: str
    identifier: str

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value.strip() or value != value.strip()
               for value in (self.family, self.dictionary, self.identifier)):
            raise ValueError("Marker identity fields must be non-empty canonical strings")

    @classmethod
    def from_mapping(cls, value: object) -> "MarkerIdentity | None":
        if value is None:
            return None
        if not isinstance(value, Mapping):
            raise ValueError("human_marker must be a table")
        expected = {"family", "dictionary", "identifier"}
        if set(value) != expected:
            raise ValueError("human_marker requires exactly family, dictionary, and identifier")
        try:
            return cls(
                family=value["family"],
                dictionary=value["dictionary"],
                identifier=value["identifier"],
            )
        except TypeError as exc:
            raise ValueError("human_marker identity values must be strings") from exc


@dataclass(frozen=True)
class RuntimeSettings:
    cm_per_second: float = 25.0
    deg_per_second: float = 360.0
    turn_speed: float = 0.5
    step_timeout_seconds: float = 6.0
    mission_timeout_seconds: float = 45.0
    max_step_retries: int = 2
    max_plan_steps: int = 20
    max_distance_cm: float = 300.0
    max_angle_deg: float = 360.0
    max_duration_sec: float = 12.0
    max_follow_duration_sec: float = 600.0
    min_stand_off_cm: float = 30.0
    max_stand_off_cm: float = 300.0
    search_timeout_seconds: float = 25.0
    timeout_margin_seconds: float = 10.0
    camera_ball_diameter_cm: float = 6.5
    camera_focal_px: float = 600.0
    camera_ultrasonic_fusion: bool = False
    backward_cm_per_second: float | None = None
    protection_presence: str = "absent"
    human_marker_identity: MarkerIdentity | None = None


@dataclass(frozen=True)
class LLMSettings:
    """Réglages du client LLM local (llama-server), surchargeables par variables d'environnement."""

    model: str = "qwen2.5-1.5b"
    connect_timeout_seconds: float = 1.0
    read_timeout_seconds: float = 10.0
    max_tokens_plan: int = 120
    max_tokens_intent: int = 96


def _env_positive(environ: Mapping[str, str], key: str, default: float, cast=float):
    try:
        value = cast(environ[key])
    except (KeyError, TypeError, ValueError):
        return default
    return value if value > 0 else default


def load_llm_settings(environ: Mapping[str, str] | None = None) -> LLMSettings:
    """Lit LLM_MODEL, LLM_CONNECT_TIMEOUT_SECONDS, LLM_READ_TIMEOUT_SECONDS,
    LLM_MAX_TOKENS_PLAN et LLM_MAX_TOKENS_INTENT ; valeur absente ou invalide -> défaut."""
    env = os.environ if environ is None else environ
    defaults = LLMSettings()
    return LLMSettings(
        model=(env.get("LLM_MODEL") or "").strip() or defaults.model,
        connect_timeout_seconds=_env_positive(env, "LLM_CONNECT_TIMEOUT_SECONDS", defaults.connect_timeout_seconds),
        read_timeout_seconds=_env_positive(env, "LLM_READ_TIMEOUT_SECONDS", defaults.read_timeout_seconds),
        max_tokens_plan=_env_positive(env, "LLM_MAX_TOKENS_PLAN", defaults.max_tokens_plan, int),
        max_tokens_intent=_env_positive(env, "LLM_MAX_TOKENS_INTENT", defaults.max_tokens_intent, int),
    )


def _config_file() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "runtime_calibration.toml"


def load_runtime_settings() -> RuntimeSettings:
    path = _config_file()
    if not path.exists():
        return RuntimeSettings()

    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    runtime = raw.get("runtime", {})
    limits = raw.get("limits", {})
    camera = raw.get("camera", {})
    marker_identity = MarkerIdentity.from_mapping(raw.get("human_marker"))
    presence = raw.get("protection", {}).get("presence", "absent")
    if presence not in {"absent", "present"}:
        raise ValueError("Invalid protection.presence; expected absent or present")

    return RuntimeSettings(
        protection_presence=presence,
        cm_per_second=float(runtime.get("cm_per_second", 25.0)),
        backward_cm_per_second=(
            float(runtime["backward_cm_per_second"]) if "backward_cm_per_second" in runtime else None
        ),
        deg_per_second=float(runtime.get("deg_per_second", 360.0)),
        turn_speed=float(runtime.get("turn_speed", 0.5)),
        step_timeout_seconds=float(runtime.get("step_timeout_seconds", 6.0)),
        mission_timeout_seconds=float(runtime.get("mission_timeout_seconds", 45.0)),
        max_step_retries=int(runtime.get("max_step_retries", 2)),
        max_plan_steps=int(limits.get("max_plan_steps", 20)),
        max_distance_cm=float(limits.get("max_distance_cm", 300.0)),
        max_angle_deg=float(limits.get("max_angle_deg", 360.0)),
        max_duration_sec=float(limits.get("max_duration_sec", 12.0)),
        max_follow_duration_sec=float(limits.get("max_follow_duration_sec", 600.0)),
        min_stand_off_cm=float(limits.get("min_stand_off_cm", 30.0)),
        max_stand_off_cm=float(limits.get("max_stand_off_cm", 300.0)),
        search_timeout_seconds=float(runtime.get("search_timeout_seconds", 25.0)),
        timeout_margin_seconds=float(runtime.get("timeout_margin_seconds", 10.0)),
        camera_ball_diameter_cm=float(camera.get("ball_diameter_cm", 6.5)),
        camera_focal_px=float(camera.get("focal_px", 600.0)),
        camera_ultrasonic_fusion=bool(camera.get("ultrasonic_fusion", False)),
        human_marker_identity=marker_identity,
    )
