from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from irobot.config import settings
from irobot.hardware.camera import color_detector
from irobot.hardware.camera.camera_live_pipeline import CameraLivePerceptionPipeline
from irobot.hardware.camera.distance_estimator import (
    ExponentialSmoother,
    distance_reader_from_robot,
    estimate_distance_cm,
    focal_from_known_distance,
    fuse_with_ultrasound,
)
from irobot.interfaces.perception_pipeline import ObjectDetection
from tests.unit.fake_robot import FakeRobot


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


def test_distance_reader_from_robot():
    robot = FakeRobot()
    robot.ultrasound_cm = 42.0
    reader = distance_reader_from_robot(robot)
    assert reader is not None and reader() == 42.0
    assert distance_reader_from_robot(object()) is None


def _pipeline(**kwargs) -> CameraLivePerceptionPipeline:
    return CameraLivePerceptionPipeline(autostart=False, ball_diameter_cm=6.5, focal_px=600.0, **kwargs)


def _ball(position: str = "center", diameter_px: float = 39.0) -> ObjectDetection:
    return ObjectDetection(label="yellow_ball", position=position, confidence=0.95, diameter_px=diameter_px)


def test_pipeline_visual_distance_and_smoothing():
    pipe = _pipeline()
    assert pipe._compute_distance_cm(_ball(diameter_px=39.0)) == pytest.approx(100.0)
    # diamètre doublé -> mesure brute 50, lissée : 0.4*50 + 0.6*100
    assert pipe._compute_distance_cm(_ball(diameter_px=78.0)) == pytest.approx(80.0)


def test_pipeline_no_distance_for_object():
    pipe = _pipeline()
    obj = ObjectDetection(label="yellow_object", position="center", diameter_px=39.0)
    assert pipe._compute_distance_cm(obj) is None


def test_pipeline_fusion_concordant_divergent_absent_disabled():
    robot = FakeRobot()
    reader = distance_reader_from_robot(robot)

    robot.ultrasound_cm = 110.0
    assert _pipeline(distance_reader=reader)._compute_distance_cm(_ball()) == 110.0

    robot.ultrasound_cm = 200.0
    assert _pipeline(distance_reader=reader)._compute_distance_cm(_ball()) == pytest.approx(100.0)

    robot.ultrasound_cm = 110.0
    assert _pipeline(distance_reader=None)._compute_distance_cm(_ball()) == pytest.approx(100.0)
    assert _pipeline(distance_reader=reader, fusion_enabled=False)._compute_distance_cm(_ball()) == pytest.approx(100.0)
    # balle hors centre : pas de fusion
    assert _pipeline(distance_reader=reader)._compute_distance_cm(_ball("left")) == pytest.approx(100.0)


def test_pipeline_fusion_survives_sensor_error():
    def broken():
        raise RuntimeError("gpio")

    assert _pipeline(distance_reader=broken)._compute_distance_cm(_ball()) == pytest.approx(100.0)


def _synthetic_frame(radius: int, rotate: bool = False):
    frame = np.zeros((480, 640, 3), np.uint8)
    # jaune en RGB
    import cv2

    cv2.circle(frame, (320, 240), radius, (255, 220, 0), -1)
    return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE) if rotate else frame


def test_detector_diameter_is_rotation_invariant_and_chain_unchanged():
    frame = _synthetic_frame(40)
    expected = 80.0
    for rotated in (frame, _synthetic_frame(40, rotate=True)):
        cands = color_detector.detect_colored_objects(rotated, "yellow", is_rgb=True)
        assert len(cands) == 1
        assert cands[0]["diameter_px"] == pytest.approx(expected, rel=0.05)
        best = color_detector.choose_best_result(cands, "yellow", rotated.shape, robotic=True)
        assert best.startswith("BALL_YELLOW_")
        verdict, metrics = color_detector.choose_best_result_with_metrics(cands, "yellow", rotated.shape, robotic=True)
        assert verdict == best and metrics["diameter_px"] == cands[0]["diameter_px"]


def test_pipeline_process_frame_end_to_end():
    pipe = _pipeline()
    detection = pipe._process_frame(_synthetic_frame(40))
    assert detection is not None and detection.label == "yellow_ball"
    assert detection.diameter_px == pytest.approx(80.0, rel=0.05)
    assert detection.distance_cm == pytest.approx(600.0 * 6.5 / detection.diameter_px)
    assert pipe._process_frame(np.zeros((480, 640, 3), np.uint8)) is None


def test_camera_section_in_toml(tmp_path, monkeypatch):
    cfg = tmp_path / "c.toml"
    cfg.write_text("[camera]\nball_diameter_cm = 7.0\nfocal_px = 550.0\n", encoding="utf-8")
    monkeypatch.setattr(settings, "_config_file", lambda: cfg)
    loaded = settings.load_runtime_settings()
    assert loaded.camera_ball_diameter_cm == 7.0
    assert loaded.camera_focal_px == 550.0

    monkeypatch.setattr(settings, "_config_file", lambda: Path("/tmp/nonexistent.toml"))
    default = settings.load_runtime_settings()
    assert (default.camera_ball_diameter_cm, default.camera_focal_px) == (6.5, 600.0)
