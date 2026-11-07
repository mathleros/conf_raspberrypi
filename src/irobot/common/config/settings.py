"""Global project settings and runtime calibration."""

from __future__ import annotations

import math
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from irobot.common.config.llm_settings import LLMSettings, load_llm_settings

__all__ = [
    "LLMSettings",
    "MarkerIdentity",
    "RuntimeSettings",
    "load_llm_settings",
    "load_runtime_settings",
]

# Valeurs par défaut alignées sur runtime_settings.toml.
DEFAULT_BACKWARD_CM_PER_SECOND = 25.0
DEFAULT_CAMERA_CAPTURE_SIZE_PX = (1280, 720)
DEFAULT_CAMERA_ORIENTED_FRAME_SIZE_PX = (720, 1280)
DEFAULT_CAMERA_BALL_DIAMETER_CM = 6.2
DEFAULT_CAMERA_FOCAL_PX = 690.0
DEFAULT_CAMERA_FACE_WIDTH_CM = 8.0
DEFAULT_CAMERA_FACE_SCORE_THRESHOLD = 0.85


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
    def from_mapping(cls, value: object) -> MarkerIdentity | None:
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


def _require_number(
    name: str, value: object, expected: str, *, integer: bool = False, positive: bool = False, non_negative: bool = False,
) -> None:
    """Lève ValueError « {name} must be {expected} » sauf si value est un nombre valide (jamais un bool)."""
    valid = not isinstance(value, bool) and isinstance(value, int if integer else (int, float))
    if valid and not integer:
        try:
            valid = math.isfinite(value)
        except OverflowError:
            valid = False
    if valid and ((positive and value <= 0) or (non_negative and value < 0)):
        valid = False
    if not valid:
        raise ValueError(f"{name} must be {expected}")


@dataclass(frozen=True)
class RuntimeSettings:
    cm_per_second: float = 33.0
    deg_per_second: float = 180.0
    drive_speed: float = 0.5
    turn_speed: float = 0.5
    obstacle_threshold_cm: float = 5.0
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
    stand_off_default_cm: float = 60.0
    stand_off_tolerance_percent: float = 5.0
    search_timeout_seconds: float = 25.0
    timeout_margin_seconds: float = 10.0
    camera_capture_size_px: tuple[int, int] = DEFAULT_CAMERA_CAPTURE_SIZE_PX
    camera_oriented_frame_size_px: tuple[int, int] = DEFAULT_CAMERA_ORIENTED_FRAME_SIZE_PX
    camera_ball_diameter_cm: float = DEFAULT_CAMERA_BALL_DIAMETER_CM
    camera_focal_px: float = DEFAULT_CAMERA_FOCAL_PX
    camera_clahe_enabled: bool = True
    camera_clahe_clip_limit: float = 3.0
    camera_exposure_value: float = 1.0
    camera_face_width_cm: float = DEFAULT_CAMERA_FACE_WIDTH_CM
    camera_face_score_threshold: float = DEFAULT_CAMERA_FACE_SCORE_THRESHOLD
    camera_face_grace_frames: int = 10
    camera_edge_offset_threshold: float = 0.6
    camera_face_model_path: str = str(
        Path(__file__).resolve().parents[4] / "assets" / "vision" / "face_detection_yunet_2023mar.onnx",
    )
    camera_face_recognition_model_path: str = str(
        Path(__file__).resolve().parents[4] / "assets" / "vision" / "face_recognition_sface_2021dec.onnx",
    )
    camera_face_gallery_dir: str = str(Path(__file__).resolve().parents[4] / "assets" / "face")
    camera_face_match_threshold: float = 0.363
    camera_face_recognition_every_n: int = 5
    backward_cm_per_second: float | None = DEFAULT_BACKWARD_CM_PER_SECOND
    human_marker_identity: MarkerIdentity | None = None
    human_max_age_seconds: float = 0.2
    human_announcement_timeout_seconds: float = 2.0

    def __post_init__(self) -> None:
        for name in ("camera_capture_size_px", "camera_oriented_frame_size_px"):
            size = getattr(self, name)
            if (not isinstance(size, tuple) or len(size) != 2
                    or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
                           for value in size)):
                raise ValueError(f"{name} must contain two positive integers")
        if self.obstacle_threshold_cm < 0:
            raise ValueError("obstacle_threshold_cm must be non-negative")
        for name in ("stand_off_default_cm", "stand_off_tolerance_percent"):
            _require_number(name, getattr(self, name), "a finite positive number", positive=True)
        if not self.min_stand_off_cm <= self.stand_off_default_cm <= self.max_stand_off_cm:
            raise ValueError("stand_off_default_cm must be between min_stand_off_cm and max_stand_off_cm")
        if self.stand_off_tolerance_percent >= 100:
            raise ValueError("stand_off_tolerance_percent must be less than 100")
        for name in ("camera_face_width_cm", "camera_face_score_threshold"):
            _require_number(name, getattr(self, name), "a finite positive number", positive=True)
        if self.camera_face_score_threshold > 1:
            raise ValueError("camera_face_score_threshold must be at most 1")
        _require_number(
            "camera_edge_offset_threshold", self.camera_edge_offset_threshold, "a finite number in (0, 1]",
            positive=True,
        )
        if self.camera_edge_offset_threshold > 1:
            raise ValueError("camera_edge_offset_threshold must be at most 1")
        _require_number(
            "camera_face_grace_frames", self.camera_face_grace_frames, "a non-negative integer",
            integer=True, non_negative=True,
        )
        if not isinstance(self.camera_face_model_path, str) or not self.camera_face_model_path.strip():
            raise ValueError("camera_face_model_path must be a non-empty path string")
        for name in ("camera_face_recognition_model_path", "camera_face_gallery_dir"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty path string")
        _require_number(
            "camera_face_match_threshold", self.camera_face_match_threshold, "a finite number in (0, 1]",
            positive=True,
        )
        if self.camera_face_match_threshold > 1:
            raise ValueError("camera_face_match_threshold must be at most 1")
        _require_number(
            "camera_face_recognition_every_n", self.camera_face_recognition_every_n, "a positive integer",
            integer=True, positive=True,
        )
        if not isinstance(self.camera_clahe_enabled, bool):
            raise ValueError("camera_clahe_enabled must be a boolean")
        for name in ("camera_clahe_clip_limit", "camera_exposure_value"):
            _require_number(name, getattr(self, name), "a finite number")
        if self.camera_clahe_clip_limit <= 0:
            raise ValueError("camera_clahe_clip_limit must be positive")
        if not -8.0 <= self.camera_exposure_value <= 8.0:
            raise ValueError("camera_exposure_value must be between -8 and 8 EV")
        for name in ("human_max_age_seconds", "human_announcement_timeout_seconds"):
            _require_number(name, getattr(self, name), "a finite positive number", positive=True)


def _config_file() -> Path:
    return Path(__file__).with_name("runtime_settings.toml")


def _table(raw: Mapping[str, object], name: str, allowed: set[str]) -> Mapping[str, object]:
    value = raw.get(name, {})
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a TOML table")
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"Unknown key(s) in [{name}]: {', '.join(sorted(unknown))}")
    return value


def _float(table: Mapping[str, object], key: str, default: float, error_name: str) -> float:
    value = table.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{error_name} must be a finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{error_name} must be a finite number")
    return float(value)


def _int(table: Mapping[str, object], key: str, default: int, error_name: str) -> int:
    value = table.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{error_name} must be an integer")
    return value


def _bool(table: Mapping[str, object], key: str, default: bool, error_name: str) -> bool:
    value = table.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{error_name} must be a boolean")
    return value


def _string(table: Mapping[str, object], key: str, default: str, error_name: str) -> str:
    value = table.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{error_name} must be a non-empty string")
    return value


def _size_px(table: Mapping[str, object], key: str, default: tuple[int, int], error_name: str) -> tuple[int, int]:
    value = table.get(key, default)
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in value)):
        raise ValueError(f"{error_name} must contain two positive integers")
    return value[0], value[1]


def _load_runtime_section(raw: Mapping[str, object], current: RuntimeSettings) -> RuntimeSettings:
    table = _table(raw, "runtime", {
        "cm_per_second", "backward_cm_per_second", "deg_per_second", "drive_speed", "turn_speed",
        "obstacle_threshold_cm",
        "step_timeout_seconds", "mission_timeout_seconds", "max_step_retries",
        "search_timeout_seconds", "timeout_margin_seconds",
    })
    backward: float | None = table.get("backward_cm_per_second", current.backward_cm_per_second)
    if backward is not None:
        backward = _float(table, "backward_cm_per_second", backward, "runtime.backward_cm_per_second")
    return replace(
        current,
        cm_per_second=_float(table, "cm_per_second", current.cm_per_second, "runtime.cm_per_second"),
        backward_cm_per_second=backward,
        deg_per_second=_float(table, "deg_per_second", current.deg_per_second, "runtime.deg_per_second"),
        drive_speed=_float(table, "drive_speed", current.drive_speed, "runtime.drive_speed"),
        turn_speed=_float(table, "turn_speed", current.turn_speed, "runtime.turn_speed"),
        obstacle_threshold_cm=_float(
            table, "obstacle_threshold_cm", current.obstacle_threshold_cm, "runtime.obstacle_threshold_cm",
        ),
        step_timeout_seconds=_float(table, "step_timeout_seconds", current.step_timeout_seconds, "runtime.step_timeout_seconds"),
        mission_timeout_seconds=_float(table, "mission_timeout_seconds", current.mission_timeout_seconds, "runtime.mission_timeout_seconds"),
        max_step_retries=_int(table, "max_step_retries", current.max_step_retries, "runtime.max_step_retries"),
        search_timeout_seconds=_float(table, "search_timeout_seconds", current.search_timeout_seconds, "runtime.search_timeout_seconds"),
        timeout_margin_seconds=_float(table, "timeout_margin_seconds", current.timeout_margin_seconds, "runtime.timeout_margin_seconds"),
    )


def _load_limits_section(raw: Mapping[str, object], current: RuntimeSettings) -> RuntimeSettings:
    table = _table(raw, "limits", {
        "max_plan_steps", "max_distance_cm", "max_angle_deg", "max_duration_sec",
        "max_follow_duration_sec", "min_stand_off_cm", "max_stand_off_cm",
    })
    return replace(
        current,
        max_plan_steps=_int(table, "max_plan_steps", current.max_plan_steps, "limits.max_plan_steps"),
        max_distance_cm=_float(table, "max_distance_cm", current.max_distance_cm, "limits.max_distance_cm"),
        max_angle_deg=_float(table, "max_angle_deg", current.max_angle_deg, "limits.max_angle_deg"),
        max_duration_sec=_float(table, "max_duration_sec", current.max_duration_sec, "limits.max_duration_sec"),
        max_follow_duration_sec=_float(table, "max_follow_duration_sec", current.max_follow_duration_sec, "limits.max_follow_duration_sec"),
        min_stand_off_cm=_float(table, "min_stand_off_cm", current.min_stand_off_cm, "limits.min_stand_off_cm"),
        max_stand_off_cm=_float(table, "max_stand_off_cm", current.max_stand_off_cm, "limits.max_stand_off_cm"),
    )


def _load_stand_off_section(raw: Mapping[str, object], current: RuntimeSettings) -> RuntimeSettings:
    table = _table(raw, "stand_off", {"default_cm", "tolerance_percent"})
    return replace(
        current,
        stand_off_default_cm=_float(table, "default_cm", current.stand_off_default_cm, "stand_off.default_cm"),
        stand_off_tolerance_percent=_float(
            table, "tolerance_percent", current.stand_off_tolerance_percent, "stand_off.tolerance_percent",
        ),
    )


def _load_camera_section(
    raw: Mapping[str, object], current: RuntimeSettings, config_path: Path,
) -> RuntimeSettings:
    table = _table(raw, "camera", {
        "capture_size_px", "oriented_frame_size_px", "ball_diameter_cm", "focal_px", "exposure_value",
        "clahe_enabled", "clahe_clip_limit", "face_model_path", "face_width_cm",
        "face_score_threshold", "face_grace_frames", "edge_offset_threshold",
        "face_recognition_model_path", "face_gallery_dir", "face_match_threshold",
        "face_recognition_every_n",
    })
    model_path = Path(_string(
        table, "face_model_path", current.camera_face_model_path, "camera_face_model_path",
    ))
    if not model_path.is_absolute():
        model_path = config_path.parent / model_path
    recognition_path = Path(_string(
        table, "face_recognition_model_path", current.camera_face_recognition_model_path,
        "camera_face_recognition_model_path",
    ))
    if not recognition_path.is_absolute():
        recognition_path = config_path.parent / recognition_path
    gallery_dir = Path(_string(table, "face_gallery_dir", current.camera_face_gallery_dir, "camera_face_gallery_dir"))
    if not gallery_dir.is_absolute():
        gallery_dir = config_path.parent / gallery_dir
    return replace(
        current,
        camera_face_recognition_model_path=str(recognition_path),
        camera_face_gallery_dir=str(gallery_dir),
        camera_face_match_threshold=_float(
            table, "face_match_threshold", current.camera_face_match_threshold, "camera_face_match_threshold",
        ),
        camera_face_recognition_every_n=_int(
            table, "face_recognition_every_n", current.camera_face_recognition_every_n,
            "camera_face_recognition_every_n",
        ),
        camera_capture_size_px=_size_px(
            table, "capture_size_px", current.camera_capture_size_px, "camera.capture_size_px",
        ),
        camera_oriented_frame_size_px=_size_px(
            table, "oriented_frame_size_px", current.camera_oriented_frame_size_px,
            "camera.oriented_frame_size_px",
        ),
        camera_ball_diameter_cm=_float(table, "ball_diameter_cm", current.camera_ball_diameter_cm, "camera_ball_diameter_cm"),
        camera_focal_px=_float(table, "focal_px", current.camera_focal_px, "camera_focal_px"),
        camera_clahe_enabled=_bool(table, "clahe_enabled", current.camera_clahe_enabled, "camera_clahe_enabled"),
        camera_clahe_clip_limit=_float(table, "clahe_clip_limit", current.camera_clahe_clip_limit, "camera_clahe_clip_limit"),
        camera_exposure_value=_float(table, "exposure_value", current.camera_exposure_value, "camera_exposure_value"),
        camera_face_width_cm=_float(table, "face_width_cm", current.camera_face_width_cm, "camera_face_width_cm"),
        camera_face_score_threshold=_float(table, "face_score_threshold", current.camera_face_score_threshold, "camera_face_score_threshold"),
        camera_face_grace_frames=_int(table, "face_grace_frames", current.camera_face_grace_frames, "camera_face_grace_frames"),
        camera_edge_offset_threshold=_float(
            table, "edge_offset_threshold", current.camera_edge_offset_threshold, "camera_edge_offset_threshold",
        ),
        camera_face_model_path=str(model_path),
    )


def _load_optional_sections(raw: Mapping[str, object], current: RuntimeSettings) -> RuntimeSettings:
    human_follow = _table(raw, "human_follow", {"max_age_seconds", "announcement_timeout_seconds"})
    return replace(
        current,
        human_marker_identity=MarkerIdentity.from_mapping(raw.get("human_marker")),
        human_max_age_seconds=_float(
            human_follow, "max_age_seconds", current.human_max_age_seconds, "human_follow.max_age_seconds",
        ),
        human_announcement_timeout_seconds=_float(
            human_follow, "announcement_timeout_seconds", current.human_announcement_timeout_seconds,
            "human_follow.announcement_timeout_seconds",
        ),
    )


def load_runtime_settings() -> RuntimeSettings:
    path = _config_file()
    if not path.exists():
        return RuntimeSettings()

    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("Configuration TOML must contain a table")
    allowed_sections = {"runtime", "limits", "stand_off", "camera", "human_follow", "human_marker"}
    unknown = set(raw) - allowed_sections
    if unknown:
        raise ValueError(f"Unknown top-level key(s): {', '.join(sorted(unknown))}")

    settings = RuntimeSettings()
    settings = _load_runtime_section(raw, settings)
    settings = _load_limits_section(raw, settings)
    settings = _load_stand_off_section(raw, settings)
    settings = _load_camera_section(raw, settings, path)
    return _load_optional_sections(raw, settings)
