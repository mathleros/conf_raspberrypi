from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from irobot.common.config import settings
from irobot.common.hardware.camera.detector import color_detector
from irobot.common.hardware.camera.camera_live_perception_pipeline import (
    CameraLivePerceptionPipeline,
    ExponentialSmoother,
)
from irobot.common.hardware.camera.detector import ColorDetector, Detector
from irobot.common.hardware.camera.detector.distance_estimator import estimate_distance_cm
from irobot.common.domain.perception import PerceptionTarget
from irobot.common.interfaces.perception_contracts import (
    ObjectDetection,
)
from irobot.common.tools.calibrate_distance import focal_from_known_distance
from tests.unit.perception_helpers import camera_target


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


def _pipeline(**kwargs) -> CameraLivePerceptionPipeline:
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


def test_pipeline_smooths_color_detector_distance_and_resets_on_lost_target():
    pipe = _pipeline()
    strategy = camera_target(pipe, "yellow")
    first = pipe._process_frame(_synthetic_frame(40), target=strategy)
    second = pipe._process_frame(_synthetic_frame(80), target=strategy)
    assert first.distance_cm == pytest.approx(600.0 * 6.5 / first.diameter_px)
    assert second.distance_cm == pytest.approx(
        0.4 * (600.0 * 6.5 / second.diameter_px)
        + 0.6 * (600.0 * 6.5 / first.diameter_px),
    )
    assert pipe._process_frame(np.zeros((480, 640, 3), np.uint8), target=strategy) is None
    third = pipe._process_frame(_synthetic_frame(40), target=strategy)
    assert third.distance_cm == pytest.approx(600.0 * 6.5 / third.diameter_px)


def test_pipeline_smooths_distance_for_any_strategy_and_resets_on_lost_detection():
    class ScriptedDetector:
        def __init__(self):
            second_detection = ObjectDetection(distance_cm=200.0, distance_visual_cm=200.0)
            self.second_detection = second_detection
            self.original_detections = [
                ObjectDetection(distance_cm=100.0, distance_visual_cm=100.0),
                second_detection,
                None,
                ObjectDetection(distance_cm=50.0, distance_visual_cm=50.0),
            ]

        def detect(self, frame_rgb, target):
            return self.original_detections.pop(0)

        def reset(self, target):
            pass

    detector = ScriptedDetector()
    pipe = _pipeline(detector=detector)
    frame = np.zeros((480, 640, 3), np.uint8)
    target = PerceptionTarget.FACE

    first = pipe._process_frame(frame, target=target)
    second = pipe._process_frame(frame, target=target)
    assert first.distance_cm == 100.0
    assert second.distance_cm == pytest.approx(140.0)
    assert second.distance_visual_cm == pytest.approx(140.0)
    assert detector.second_detection.distance_cm == 200.0
    assert pipe._process_frame(frame, target=target) is None
    after_loss = pipe._process_frame(frame, target=target)
    assert after_loss.distance_cm == 50.0


def test_detect_returns_visual_distance_without_mutating_published_detection():
    pipe = _pipeline()
    strategy = camera_target(pipe, "yellow")
    pipe.detect(target=strategy)
    _publish(pipe, _ball())
    assert pipe.detect(target=strategy).distance_cm == pytest.approx(100.0)
    assert pipe._last_detection.distance_cm == pytest.approx(100.0)


def _synthetic_frame(radius: int, rotate: bool = False):
    frame = np.zeros((480, 640, 3), np.uint8)
    # jaune en RGB
    import cv2

    cv2.circle(frame, (320, 240), radius, (255, 220, 0), -1)
    return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE) if rotate else frame


def test_detector_diameter_is_rotation_invariant_and_selects_largest_ball():
    frame = _synthetic_frame(40)
    expected = 80.0
    for rotated in (frame, _synthetic_frame(40, rotate=True)):
        cands = color_detector.detect_colored_balls(rotated, "yellow", is_rgb=True)
        assert len(cands) == 1
        assert cands[0]["diameter_px"] == pytest.approx(expected, rel=0.05)
        selected = color_detector.select_largest_ball(cands)
        assert selected == cands[0]
        assert selected["diameter_px"] == cands[0]["diameter_px"]


def test_ball_selection_returns_largest_ball_or_none():
    candidates = [
        {"bbox": (40, 40, 10, 10), "area": 400, "diameter_px": 23},
        {"bbox": (70, 70, 15, 15), "area": 500, "diameter_px": 25},
    ]
    assert color_detector.select_largest_ball(candidates) is candidates[1]
    assert color_detector.select_largest_ball(candidates[:1]) is candidates[0]
    assert color_detector.select_largest_ball([]) is None


def test_pipeline_process_frame_end_to_end():
    pipe = _pipeline()
    strategy = camera_target(pipe, "yellow")
    detection = pipe._process_frame(_synthetic_frame(40), target=strategy)
    assert detection is not None and detection.label == "yellow_ball"
    assert detection.diameter_px == pytest.approx(80.0, rel=0.05)
    assert detection.distance_cm == pytest.approx(600.0 * 6.5 / detection.diameter_px)
    assert pipe._process_frame(np.zeros((480, 640, 3), np.uint8), target=strategy) is None


@pytest.mark.parametrize(("center_x", "position"), [
    (159, "left"), (160, "center"), (320, "center"), (321, "right"),
])
def test_pipeline_preserves_horizontal_position_thresholds(monkeypatch, center_x, position):
    pipe = _pipeline()
    candidate = {
        "bbox": (center_x - 10, 100, 20, 20),
        "area": 300.0, "diameter_px": 20.0,
    }
    monkeypatch.setattr(
        color_detector, "detect_colored_balls", lambda *args, **kwargs: [candidate],
    )
    detection = pipe._process_frame(
        np.zeros((640, 480, 3), np.uint8), target=camera_target(pipe, "red")
    )
    assert detection is not None
    assert detection.position == position


@pytest.mark.parametrize("target", [None, "", "blue", "object"])
def test_unknown_target_is_rejected_before_selecting_a_strategy(target):
    assert PerceptionTarget.from_value(target) is None


def test_color_target_does_not_try_other_color(monkeypatch):
    pipe = _pipeline()
    red_target = camera_target(pipe, "red")
    color_detector = pipe._detector._color_detectors[red_target]
    monkeypatch.setattr(color_detector, "detect", lambda image: None)
    yellow_target = camera_target(pipe, "yellow")
    monkeypatch.setattr(
        pipe._detector._color_detectors[yellow_target],
        "detect",
        lambda image: pytest.fail("Red strategy must not try yellow detection"),
    )

    assert pipe._process_frame(
        np.zeros((480, 640, 3), np.uint8),
        target=red_target,
    ) is None


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
