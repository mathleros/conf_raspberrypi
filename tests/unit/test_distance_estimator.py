from __future__ import annotations

from pathlib import Path
import threading

import numpy as np
import pytest

from irobot.config import settings
from irobot.hardware.camera.detector import color_detector
from irobot.hardware.camera.camera_live_pipeline import CameraLivePerceptionPipeline
from irobot.hardware.camera.detector import ColorDetector, Detector
from irobot.hardware.camera.distance_estimator import (
    ExponentialSmoother,
    estimate_distance_cm,
    focal_from_known_distance,
    fuse_with_ultrasound,
)
from irobot.interfaces.perception_pipeline import ObjectDetection


def test_estimate_distance_known_values():
    assert estimate_distance_cm(39.0, 6.5, 600.0) == pytest.approx(100.0)
    assert estimate_distance_cm(78.0, 6.5, 600.0) == pytest.approx(50.0)


@pytest.mark.parametrize("diameter", [0, -5.0, None, float("nan"), float("inf"), "abc"])
def test_estimate_distance_invalid_diameter(diameter):
    assert estimate_distance_cm(diameter, 6.5, 600.0) is None


def test_estimate_distance_invalid_calibration():
    assert estimate_distance_cm(40.0, 0.0, 600.0) is None
    assert estimate_distance_cm(40.0, 6.5, -1.0) is None


def test_focal_from_known_distance_roundtrip():
    focal = focal_from_known_distance(39.0, 6.5, 100.0)
    assert focal == pytest.approx(600.0)
    assert estimate_distance_cm(39.0, 6.5, focal) == pytest.approx(100.0)
    assert focal_from_known_distance(0.0, 6.5, 100.0) is None


def test_smoother_exponential_and_reset():
    smoother = ExponentialSmoother(alpha=0.4)
    assert smoother.update(100.0) == 100.0
    assert smoother.update(200.0) == pytest.approx(140.0)
    assert smoother.update(None) is None
    assert smoother.update(50.0) == 50.0
    with pytest.raises(ValueError):
        ExponentialSmoother(alpha=0.0)


def test_fusion_concordant_divergent_and_missing():
    assert fuse_with_ultrasound(100.0, 110.0) == 110.0
    assert fuse_with_ultrasound(100.0, 125.0) == 125.0
    assert fuse_with_ultrasound(100.0, 160.0) == 100.0
    assert fuse_with_ultrasound(100.0, None) == 100.0
    assert fuse_with_ultrasound(None, 100.0) is None


def _pipeline(**kwargs) -> CameraLivePerceptionPipeline:
    kwargs.setdefault("fusion_enabled", True)
    return CameraLivePerceptionPipeline(autostart=False, ball_diameter_cm=6.5, focal_px=600.0, **kwargs)


def _ball(position: str = "center", diameter_px: float = 39.0) -> ObjectDetection:
    distance = estimate_distance_cm(diameter_px, 6.5, 600.0)
    return ObjectDetection(
        label="yellow_ball", position=position, confidence=0.95, diameter_px=diameter_px,
        distance_cm=distance, distance_visual_cm=distance,
    )


def _publish(pipe: CameraLivePerceptionPipeline, detection: ObjectDetection) -> None:
    pipe._last_detection = detection


def test_color_detector_returns_visual_distance_and_common_contract():
    detector = ColorDetector("yellow", ball_diameter_cm=6.5, focal_px=600.0)
    detection = detector.detect(_synthetic_frame(40))
    assert isinstance(detector, Detector)
    assert detection is not None
    assert detection.distance_cm == pytest.approx(600.0 * 6.5 / detection.diameter_px)
    assert detection.distance_visual_cm == detection.distance_cm
    assert detection.bbox_px is not None


def test_pipeline_smooths_detector_distance_and_resets_on_lost_target():
    pipe = _pipeline()
    first = pipe._process_frame(_synthetic_frame(40))
    second = pipe._process_frame(_synthetic_frame(80))
    assert first.distance_cm == pytest.approx(600.0 * 6.5 / first.diameter_px)
    assert second.distance_cm == pytest.approx(
        0.4 * (600.0 * 6.5 / second.diameter_px)
        + 0.6 * (600.0 * 6.5 / first.diameter_px),
    )
    assert pipe._process_frame(np.zeros((480, 640, 3), np.uint8)) is None
    third = pipe._process_frame(_synthetic_frame(40))
    assert third.distance_cm == pytest.approx(600.0 * 6.5 / third.diameter_px)


def test_detect_fusion_concordant_divergent_absent_disabled():
    ultrasound_cm = [110.0]
    reader = lambda: ultrasound_cm[0]

    def detect(**kwargs):
        pipe = _pipeline(**kwargs)
        _publish(pipe, _ball(kwargs.pop("position", "center")))
        return pipe.detect()

    assert detect(distance_reader=reader).distance_cm == 110.0
    ultrasound_cm[0] = 200.0
    assert detect(distance_reader=reader).distance_cm == pytest.approx(100.0)
    ultrasound_cm[0] = 110.0
    assert detect(distance_reader=None).distance_cm == pytest.approx(100.0)
    assert detect(distance_reader=reader, fusion_enabled=False).distance_cm == pytest.approx(100.0)

    pipe = _pipeline(distance_reader=reader)
    _publish(pipe, _ball("left"))
    assert pipe.detect().distance_cm == pytest.approx(100.0)


def test_detect_does_not_mutate_published_detection():
    pipe = _pipeline(distance_reader=lambda: 110.0)
    _publish(pipe, _ball())
    assert pipe.detect().distance_cm == 110.0
    assert pipe._last_detection.distance_cm == pytest.approx(100.0)


def test_detect_reader_exception_or_none_falls_back_to_visual():
    def broken():
        raise RuntimeError("gpio")

    for reader in (broken, lambda: None):
        pipe = _pipeline(distance_reader=reader)
        _publish(pipe, _ball())
        assert pipe.detect().distance_cm == pytest.approx(100.0)


def test_reader_called_from_detect_caller_thread_never_camera_thread():
    calls: list[threading.Thread] = []

    def reader():
        calls.append(threading.current_thread())
        return 110.0

    pipe = _pipeline(distance_reader=reader)
    pipe._stop_event.set()
    camera_thread = threading.Thread(target=lambda: _publish(pipe, _ball()))
    camera_thread.start()
    camera_thread.join()
    assert calls == []

    pipe.detect()
    assert calls == [threading.current_thread()]

    results = []
    caller = threading.Thread(target=lambda: results.append(pipe.detect()))
    caller.start()
    caller.join()
    assert calls[-1] is caller and camera_thread not in calls


def test_flag_false_reader_never_called(monkeypatch, tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text("[camera]\nultrasonic_fusion = false\n", encoding="utf-8")
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)

    def reader():
        raise AssertionError("ne doit pas être appelé")

    pipe = CameraLivePerceptionPipeline(autostart=False, distance_reader=reader, focal_px=600.0, ball_diameter_cm=6.5)
    assert pipe.fusion_enabled is False
    _publish(pipe, _ball())
    assert pipe.detect().distance_cm == pytest.approx(100.0)

    cfg.write_text("[camera]\nultrasonic_fusion = true\n", encoding="utf-8")
    assert CameraLivePerceptionPipeline(autostart=False, distance_reader=reader).fusion_enabled is True


def _synthetic_frame(radius: int, rotate: bool = False):
    frame = np.zeros((480, 640, 3), np.uint8)
    # jaune en RGB
    import cv2

    cv2.circle(frame, (320, 240), radius, (255, 220, 0), -1)
    return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE) if rotate else frame


def test_detector_diameter_is_rotation_invariant_and_candidate_selection():
    frame = _synthetic_frame(40)
    expected = 80.0
    for rotated in (frame, _synthetic_frame(40, rotate=True)):
        cands = color_detector.detect_colored_objects(rotated, "yellow", is_rgb=True)
        assert len(cands) == 1
        assert cands[0]["diameter_px"] == pytest.approx(expected, rel=0.05)
        selected = color_detector.select_best_candidate(cands)
        assert selected == cands[0]
        assert selected["kind"] == "ball"
        assert selected["diameter_px"] == cands[0]["diameter_px"]


def test_candidate_selection_prefers_largest_ball_then_largest_object():
    candidates = [
        {"kind": "object", "bbox": (10, 10, 20, 20), "area": 900, "diameter_px": 34},
        {"kind": "ball", "bbox": (40, 40, 10, 10), "area": 400, "diameter_px": 23},
        {"kind": "ball", "bbox": (70, 70, 15, 15), "area": 500, "diameter_px": 25},
    ]
    assert color_detector.select_best_candidate(candidates) is candidates[2]
    assert color_detector.select_best_candidate(candidates[:1]) is candidates[0]
    assert color_detector.select_best_candidate([]) is None


def test_pipeline_process_frame_end_to_end():
    pipe = _pipeline()
    detection = pipe._process_frame(_synthetic_frame(40))
    assert detection is not None and detection.label == "yellow_ball"
    assert detection.diameter_px == pytest.approx(80.0, rel=0.05)
    assert detection.distance_cm == pytest.approx(600.0 * 6.5 / detection.diameter_px)
    assert pipe._process_frame(np.zeros((480, 640, 3), np.uint8)) is None


@pytest.mark.parametrize(("center_x", "position"), [
    (159, "left"), (160, "center"), (320, "center"), (321, "right"),
])
def test_pipeline_preserves_horizontal_position_thresholds(monkeypatch, center_x, position):
    pipe = _pipeline()
    candidate = {
        "kind": "ball", "bbox": (center_x - 10, 100, 20, 20),
        "area": 300.0, "diameter_px": 20.0,
    }
    monkeypatch.setattr(
        color_detector, "detect_colored_objects", lambda *args, **kwargs: [candidate],
    )
    detection = pipe._process_frame(np.zeros((640, 480, 3), np.uint8), target="red")
    assert detection is not None
    assert detection.position == position


def test_camera_section_in_toml(tmp_path, monkeypatch):
    cfg = tmp_path / "c.toml"
    cfg.write_text("[camera]\nball_diameter_cm = 7.0\nfocal_px = 550.0\n", encoding="utf-8")
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)
    loaded = settings.load_runtime_settings()
    assert loaded.camera_ball_diameter_cm == 7.0
    assert loaded.camera_focal_px == 550.0

    monkeypatch.setattr(settings, "_config_file", lambda: Path("/tmp/nonexistent.toml"))
    default = settings.load_runtime_settings()
    assert (default.camera_ball_diameter_cm, default.camera_focal_px) == (6.0, 680.0)
    assert default.camera_ultrasonic_fusion is False
