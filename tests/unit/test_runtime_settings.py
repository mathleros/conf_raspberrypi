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
    assert loaded.backward_cm_per_second is None
    assert loaded.deg_per_second == 150.0
    assert loaded.step_timeout_seconds == 3.5
    assert loaded.mission_timeout_seconds == 20.0
    assert loaded.max_step_retries == 1
    assert loaded.max_plan_steps == 10
    assert loaded.max_distance_cm == 180.0
    assert loaded.max_angle_deg == 120.0
    assert loaded.max_duration_sec == 8.0


def test_runtime_settings_new_defaults_without_file(monkeypatch):
    monkeypatch.setattr(settings, "_config_file", lambda: Path("/tmp/nonexistent_runtime_calibration.toml"))

    loaded = settings.load_runtime_settings()

    assert loaded.max_follow_duration_sec == 600.0
    assert loaded.min_stand_off_cm == 30.0
    assert loaded.max_stand_off_cm == 300.0
    assert loaded.search_timeout_seconds == 25.0
    assert loaded.timeout_margin_seconds == 10.0


def test_load_runtime_settings_reads_new_keys(monkeypatch, tmp_path):
    toml_file = tmp_path / "calib.toml"
    toml_file.write_text(
        "[runtime]\n"
        "search_timeout_seconds = 11.0\n"
        "timeout_margin_seconds = 3.0\n"
        "[limits]\n"
        "max_follow_duration_sec = 120.0\n"
        "min_stand_off_cm = 40.0\n"
        "max_stand_off_cm = 250.0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "_config_file", lambda: toml_file)

    loaded = settings.load_runtime_settings()

    assert loaded.max_follow_duration_sec == 120.0
    assert loaded.min_stand_off_cm == 40.0
    assert loaded.max_stand_off_cm == 250.0
    assert loaded.search_timeout_seconds == 11.0
    assert loaded.timeout_margin_seconds == 3.0


def test_empty_toml_matches_dataclass_defaults(tmp_path, monkeypatch):
    cfg = tmp_path / "runtime_calibration.toml"
    cfg.write_text("", encoding="utf-8")
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)
    monkey_default = settings.RuntimeSettings()
    loaded = settings.load_runtime_settings()

    assert loaded == monkey_default


def test_load_separate_backward_calibration(tmp_path, monkeypatch):
    cfg = tmp_path / "calibration.toml"
    cfg.write_text("[runtime]\ncm_per_second = 55.0\nbackward_cm_per_second = 25.0\n")
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)

    loaded = settings.load_runtime_settings()

    assert loaded.cm_per_second == 55.0
    assert loaded.backward_cm_per_second == 25.0
