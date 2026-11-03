from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from irobot.config import settings
from irobot.hardware.camera.detector import color_detector
from irobot.hardware.camera.camera_live_perception_pipeline import CameraLivePerceptionPipeline
from irobot.hardware.camera.detector import ColorDetector, Detector
from irobot.hardware.camera.detector.distance_estimator import estimate_distance_cm
from irobot.hardware.camera.frame_processor import ExponentialSmoother
from irobot.interfaces.perception_contracts import ObjectDetection
from irobot.tools.calibrate_distance import focal_from_known_distance


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


def test_pipeline_smooths_detector_distance_and_resets_on_lost_target():
    pipe = _pipeline()
    first = pipe._process_frame(_synthetic_frame(40), target="yellow")
    second = pipe._process_frame(_synthetic_frame(80), target="yellow")
    assert first.distance_cm == pytest.approx(600.0 * 6.5 / first.diameter_px)
    assert second.distance_cm == pytest.approx(
        0.4 * (600.0 * 6.5 / second.diameter_px)
        + 0.6 * (600.0 * 6.5 / first.diameter_px),
    )
    assert pipe._process_frame(np.zeros((480, 640, 3), np.uint8), target="yellow") is None
    third = pipe._process_frame(_synthetic_frame(40), target="yellow")
    assert third.distance_cm == pytest.approx(600.0 * 6.5 / third.diameter_px)


def test_detect_returns_visual_distance_without_mutating_published_detection():
    pipe = _pipeline()
    pipe.detect(target="yellow")
    _publish(pipe, _ball())
    assert pipe.detect(target="yellow").distance_cm == pytest.approx(100.0)
    assert pipe._last_detection.distance_cm == pytest.approx(100.0)


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
    detection = pipe._process_frame(_synthetic_frame(40), target="yellow")
    assert detection is not None and detection.label == "yellow_ball"
    assert detection.diameter_px == pytest.approx(80.0, rel=0.05)
    assert detection.distance_cm == pytest.approx(600.0 * 6.5 / detection.diameter_px)
    assert pipe._process_frame(np.zeros((480, 640, 3), np.uint8), target="yellow") is None


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


@pytest.mark.parametrize("target", [None, "", "blue", "object"])
def test_unknown_target_does_not_try_another_detector(monkeypatch, target):
    pipe = _pipeline()
    monkeypatch.setattr(
        pipe._frame_processor._marker_detector,
        "detect",
        lambda image: pytest.fail("Unknown target must not try ArUco"),
    )
    for detector in pipe._frame_processor._color_detectors.values():
        monkeypatch.setattr(
            detector,
            "detect",
            lambda image: pytest.fail("Unknown target must not try color detection"),
        )

    assert pipe._frame_processor.process_frame(
        np.zeros((480, 640, 3), np.uint8),
        target=target,
    ) is None


def test_color_target_does_not_try_other_color(monkeypatch):
    pipe = _pipeline()
    monkeypatch.setattr(pipe._frame_processor._color_detectors["red"], "detect", lambda image: None)
    monkeypatch.setattr(
        pipe._frame_processor._color_detectors["yellow"],
        "detect",
        lambda image: pytest.fail("Red target must not try yellow detection"),
    )

    assert pipe._frame_processor.process_frame(
        np.zeros((480, 640, 3), np.uint8),
        target="red",
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
