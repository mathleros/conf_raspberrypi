from __future__ import annotations

from pathlib import Path

import pytest

from irobot.common.config import settings
from irobot.common.config.llm_settings import LLMSettings as SeparateLLMSettings
from irobot.common.config.llm_settings import load_llm_settings as load_separate_llm_settings


def test_runtime_recovery_attempts_default_and_loaded(tmp_path, monkeypatch):
    assert settings.RuntimeSettings().target_recovery_attempts == 1
    cfg = tmp_path / "runtime_settings.toml"
    cfg.write_text("[runtime]\ntarget_recovery_attempts = 3\n")
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)
    assert settings.load_runtime_settings().target_recovery_attempts == 3
    for value in ("-1", "1.5"):
        cfg.write_text(f"[runtime]\ntarget_recovery_attempts = {value}\n")
        with pytest.raises(ValueError, match="target_recovery_attempts"):
            settings.load_runtime_settings()


def test_target_loss_and_align_settle_settings(tmp_path, monkeypatch):
    defaults = settings.RuntimeSettings()
    assert (defaults.target_loss_wait_seconds, defaults.align_settle_seconds,
            defaults.target_recovery_window_seconds) == (2.0, 0.4, 1.5)
    cfg = tmp_path / "runtime_settings.toml"
    cfg.write_text(
        "[runtime]\ntarget_loss_wait_seconds = 0.5\nalign_settle_seconds = 0.2\ntarget_recovery_window_seconds = 1.0\n",
    )
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)
    loaded = settings.load_runtime_settings()
    assert (loaded.target_loss_wait_seconds, loaded.align_settle_seconds,
            loaded.target_recovery_window_seconds) == (0.5, 0.2, 1.0)
    invalid = (
        "target_loss_wait_seconds = 0",
        "target_recovery_window_seconds = 0",
        "align_settle_seconds = -0.1",
        "align_settle_seconds = 1.0\ntarget_recovery_window_seconds = 0.5",
    )
    for lines in invalid:
        cfg.write_text(f"[runtime]\n{lines}\n")
        with pytest.raises(ValueError):
            settings.load_runtime_settings()


def test_load_runtime_settings_defaults_when_file_missing(monkeypatch):
    monkeypatch.setattr(settings, "_config_file", lambda: Path("/tmp/nonexistent_runtime_settings.toml"))

    loaded = settings.load_runtime_settings()

    assert loaded == settings.RuntimeSettings()


def test_load_runtime_settings_uses_packaged_calibration():
    settings_path = Path(settings.__file__).resolve()
    calibration_path = settings_path.with_name("runtime_settings.toml")
    loaded = settings.load_runtime_settings()

    assert settings._config_file().resolve() == calibration_path
    assert calibration_path.is_file()
    expected = {
        "cm_per_second": 33.0,
        "backward_cm_per_second": 25.0,
        "deg_per_second": 180.0,
        "drive_speed": 0.5,
        "turn_speed": 0.5,
        "obstacle_threshold_cm": 5.0,
        "step_timeout_seconds": 6.0,
        "mission_timeout_seconds": 45.0,
        "max_step_retries": 2,
        "max_plan_steps": 20,
        "max_distance_cm": 300.0,
        "max_angle_deg": 360.0,
        "max_duration_sec": 12.0,
        "max_follow_duration_sec": 600.0,
        "min_stand_off_cm": 30.0,
        "max_stand_off_cm": 300.0,
        "search_timeout_seconds": 25.0,
        "timeout_margin_seconds": 10.0,
        "camera_capture_size_px": (1280, 720),
        "camera_oriented_frame_size_px": (720, 1280),
        "camera_ball_diameter_cm": 6.2,
        "camera_focal_px": 1394.2,
        "camera_clahe_enabled": True,
        "camera_clahe_clip_limit": 3.0,
        "camera_exposure_value": 1.0,
        "camera_face_width_cm": 8.0,
        "camera_face_score_threshold": 0.85,
        "camera_face_grace_frames": 8,
        "camera_edge_offset_threshold": 0.55,
        "human_max_age_seconds": 0.2,
        "human_announcement_timeout_seconds": 2.0,
    }
    assert {name: getattr(loaded, name) for name in expected} == expected
    assert Path(loaded.camera_face_model_path).resolve().is_file()


def test_runtime_loader_rejects_unknown_top_level_and_section_keys(tmp_path, monkeypatch):
    cfg = tmp_path / "runtime_settings.toml"
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)

    cfg.write_text("[runtime]\ncm_per_sec = 33.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"Unknown key\(s\) in \[runtime\].*cm_per_sec"):
        settings.load_runtime_settings()

    cfg.write_text("[camera]\nultrasonic_fusion = false\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"Unknown key\(s\) in \[camera\].*ultrasonic_fusion"):
        settings.load_runtime_settings()

    cfg.write_text("unexpected = true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown top-level key.*unexpected"):
        settings.load_runtime_settings()


@pytest.mark.parametrize(
    ("toml", "error"),
    [
        ("[camera]\nclahe_enabled = 1\n", "camera_clahe_enabled"),
        ('[camera]\nfocal_px = "680"\n', "camera_focal_px"),
        ("[limits]\nmax_plan_steps = 1.5\n", "limits.max_plan_steps"),
        ("[runtime]\nobstacle_threshold_cm = -1.0\n", "obstacle_threshold_cm"),
        ("[human_follow]\nmax_age_seconds = true\n", "human_follow.max_age_seconds"),
        ("[camera]\nfocal_px = nan\n", "camera_focal_px"),
        ("[camera]\ncapture_size_px = [640, 0]\n", "camera.capture_size_px"),
        ("[camera]\noriented_frame_size_px = [480, true]\n", "camera.oriented_frame_size_px"),
        ("[camera]\nedge_offset_threshold = 1.5\n", "camera_edge_offset_threshold"),
        ("[camera]\nedge_offset_threshold = 0\n", "camera_edge_offset_threshold"),
    ],
)
def test_runtime_loader_rejects_wrong_toml_types(tmp_path, monkeypatch, toml, error):
    cfg = tmp_path / "runtime_settings.toml"
    cfg.write_text(toml, encoding="utf-8")
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)

    with pytest.raises(ValueError, match=error):
        settings.load_runtime_settings()


def test_runtime_loader_requires_sections_to_be_tables(tmp_path, monkeypatch):
    cfg = tmp_path / "runtime_settings.toml"
    cfg.write_text('camera = "off"\n', encoding="utf-8")
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)

    with pytest.raises(ValueError, match="camera must be a TOML table"):
        settings.load_runtime_settings()


def test_llm_settings_have_dedicated_module_and_compatibility_exports():
    assert settings.LLMSettings is SeparateLLMSettings
    assert settings.load_llm_settings is load_separate_llm_settings


def test_load_runtime_settings_from_toml(tmp_path, monkeypatch):
    cfg = tmp_path / "runtime_settings.toml"
    cfg.write_text(
        """
[runtime]
cm_per_second = 30.0
deg_per_second = 150.0
drive_speed = 0.7
obstacle_threshold_cm = 7.5
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
    assert loaded.backward_cm_per_second == 25.0
    assert loaded.deg_per_second == 150.0
    assert loaded.drive_speed == 0.7
    assert loaded.obstacle_threshold_cm == 7.5
    assert loaded.step_timeout_seconds == 3.5
    assert loaded.mission_timeout_seconds == 20.0
    assert loaded.max_step_retries == 1
    assert loaded.max_plan_steps == 10
    assert loaded.max_distance_cm == 180.0
    assert loaded.max_angle_deg == 120.0
    assert loaded.max_duration_sec == 8.0


def test_runtime_settings_new_defaults_without_file(monkeypatch):
    monkeypatch.setattr(settings, "_config_file", lambda: Path("/tmp/nonexistent_runtime_settings.toml"))

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
    cfg = tmp_path / "runtime_settings.toml"
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


def test_camera_dimensions_from_toml(tmp_path, monkeypatch):
    cfg = tmp_path / "runtime_settings.toml"
    cfg.write_text(
        "[camera]\ncapture_size_px = [1280, 960]\noriented_frame_size_px = [960, 1280]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)

    loaded = settings.load_runtime_settings()

    assert loaded.camera_capture_size_px == (1280, 960)
    assert loaded.camera_oriented_frame_size_px == (960, 1280)


def test_backlight_defaults_match_packaged_calibration():
    defaults = settings.RuntimeSettings()
    assert defaults.camera_clahe_enabled is True
    assert defaults.camera_exposure_value == 1.0


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
    cfg = tmp_path / "runtime_settings.toml"
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
    cfg = tmp_path / "runtime_settings.toml"
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
    cfg = tmp_path / "runtime_settings.toml"
    cfg.write_text(f"[camera]\n{key} = {value}\n")
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)
    with pytest.raises(ValueError, match=f"camera_{key}"):
        settings.load_runtime_settings()


def test_stand_off_defaults_and_section_loaded(tmp_path, monkeypatch):
    defaults = settings.RuntimeSettings()
    assert defaults.stand_off_default_cm == 60.0
    assert defaults.stand_off_tolerance_percent == 5.0

    cfg = tmp_path / "runtime_settings.toml"
    cfg.write_text("[stand_off]\ndefault_cm = 80.0\ntolerance_percent = 10.0\n")
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)
    loaded = settings.load_runtime_settings()

    assert loaded.stand_off_default_cm == 80.0
    assert loaded.stand_off_tolerance_percent == 10.0


@pytest.mark.parametrize("toml", [
    "[stand_off]\ndefault_cm = 1000.0\n",
    "[stand_off]\ntolerance_percent = 0.0\n",
    "[stand_off]\ntolerance_percent = 100.0\n",
    "[stand_off]\nunknown = 1\n",
])
def test_invalid_stand_off_settings_rejected(tmp_path, monkeypatch, toml):
    cfg = tmp_path / "runtime_settings.toml"
    cfg.write_text(toml)
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)
    with pytest.raises(ValueError):
        settings.load_runtime_settings()
