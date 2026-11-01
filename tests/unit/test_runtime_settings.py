from __future__ import annotations

from pathlib import Path

import pytest

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


def test_backlight_settings_from_toml(tmp_path, monkeypatch):
    cfg = tmp_path / "calibration.toml"
    cfg.write_text(
        "[camera]\nclahe_enabled = true\nclahe_clip_limit = 2.5\nexposure_value = 1.5\n",
    )
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)
    loaded = settings.load_runtime_settings()
    assert loaded.camera_clahe_enabled is True
    assert loaded.camera_clahe_clip_limit == 2.5
    assert loaded.camera_exposure_value == 1.5


def test_backlight_defaults_preserve_uncorrected_frames():
    defaults = settings.RuntimeSettings()
    assert defaults.camera_clahe_enabled is False
    assert defaults.camera_exposure_value == 0.0


@pytest.mark.parametrize("key,value", [
    ("clahe_enabled", '"false"'),
    ("clahe_enabled", "1"),
    ("clahe_clip_limit", "0"),
    ("clahe_clip_limit", "-1.0"),
    ("clahe_clip_limit", "nan"),
    ("clahe_clip_limit", "inf"),
    ("clahe_clip_limit", "true"),
    ("clahe_clip_limit", '"3.0"'),
    ("exposure_value", "nan"),
    ("exposure_value", "inf"),
    ("exposure_value", "8.1"),
    ("exposure_value", "-8.1"),
    ("exposure_value", "false"),
    ("exposure_value", '"1.0"'),
])
def test_invalid_backlight_settings_are_rejected(tmp_path, monkeypatch, key, value):
    cfg = tmp_path / "calibration.toml"
    cfg.write_text(f"[camera]\n{key} = {value}\n")
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)
    with pytest.raises(ValueError, match=f"camera_{key}"):
        settings.load_runtime_settings()


def test_face_settings_and_relative_model_path(tmp_path, monkeypatch):
    cfg = tmp_path / "runtime_calibration.toml"
    cfg.write_text(
        '[camera]\nface_model_path = "models/yunet.onnx"\nface_width_cm = 12.0\n'
        "face_score_threshold = 0.8\nface_grace_frames = 4\n",
    )
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)
    loaded = settings.load_runtime_settings()
    assert loaded.camera_face_model_path == str(tmp_path / "models" / "yunet.onnx")
    assert loaded.camera_face_width_cm == 12
    assert loaded.camera_face_score_threshold == 0.8
    assert loaded.camera_face_grace_frames == 4


def test_absolute_face_model_path_preserved(tmp_path, monkeypatch):
    model = tmp_path / "yunet.onnx"
    cfg = tmp_path / "runtime_calibration.toml"
    cfg.write_text(f'[camera]\nface_model_path = "{model}"\n')
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)
    assert settings.load_runtime_settings().camera_face_model_path == str(model)


@pytest.mark.parametrize("key,value", [
    ("face_width_cm", "0"), ("face_width_cm", "-1"),
    ("face_width_cm", "nan"), ("face_width_cm", "true"),
    ("face_width_cm", '"15"'),
    ("face_score_threshold", "0"), ("face_score_threshold", "1.1"),
    ("face_score_threshold", "inf"), ("face_score_threshold", "false"),
    ("face_grace_frames", "-1"), ("face_grace_frames", "1.5"),
    ("face_grace_frames", "true"), ("face_grace_frames", '"10"'),
    ("face_model_path", '""'), ("face_model_path", '"  "'),
    ("face_model_path", "false"),
])
def test_invalid_face_settings_rejected(tmp_path, monkeypatch, key, value):
    cfg = tmp_path / "runtime_calibration.toml"
    cfg.write_text(f"[camera]\n{key} = {value}\n")
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)
    with pytest.raises(ValueError, match=f"camera_{key}"):
        settings.load_runtime_settings()
