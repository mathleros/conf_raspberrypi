"""Global project settings and runtime calibration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

DEFAULT_SPEED = 0.5
DEFAULT_TIMEOUT_SECONDS = 2.0


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


def _config_file() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "runtime_calibration.toml"


def load_runtime_settings() -> RuntimeSettings:
    path = _config_file()
    if not path.exists():
        return RuntimeSettings()

    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    runtime = raw.get("runtime", {})
    limits = raw.get("limits", {})

    return RuntimeSettings(
        cm_per_second=float(runtime.get("cm_per_second", 25.0)),
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
    )
