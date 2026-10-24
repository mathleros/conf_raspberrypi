from __future__ import annotations

from pathlib import Path

from irobot.config import settings


def test_load_runtime_settings_defaults_when_file_missing(monkeypatch):
    monkeypatch.setattr(settings, "_config_file", lambda: Path("/tmp/nonexistent_runtime_calibration.toml"))

    loaded = settings.load_runtime_settings()

    assert loaded.cm_per_second > 0
    assert loaded.deg_per_second > 0
    assert loaded.max_plan_steps >= 1


def test_load_runtime_settings_from_toml(tmp_path, monkeypatch):
    cfg = tmp_path / "runtime_calibration.toml"
    cfg.write_text(
        """
[runtime]
cm_per_second = 30.0
deg_per_second = 150.0
step_timeout_seconds = 3.5
mission_timeout_seconds = 20.0
max_step_retries = 1

[limits]
max_plan_steps = 10
max_distance_cm = 180.0
max_angle_deg = 120.0
max_duration_sec = 8.0
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)

    loaded = settings.load_runtime_settings()

    assert loaded.cm_per_second == 30.0
    assert loaded.deg_per_second == 150.0
    assert loaded.step_timeout_seconds == 3.5
    assert loaded.mission_timeout_seconds == 20.0
    assert loaded.max_step_retries == 1
    assert loaded.max_plan_steps == 10
    assert loaded.max_distance_cm == 180.0
    assert loaded.max_angle_deg == 120.0
    assert loaded.max_duration_sec == 8.0
