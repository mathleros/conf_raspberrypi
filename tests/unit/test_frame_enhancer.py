from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from irobot.config.settings import RuntimeSettings
from irobot.hardware.camera import camera_live_perception_pipeline, frame_enhancer
from irobot.hardware.camera.frame_enhancer import FrameEnhancer, configure_exposure
from tests.unit.perception_helpers import camera_target


def _settings(**kwargs):
    return RuntimeSettings(camera_clahe_enabled=True, **kwargs)


def test_disabled_enhancer_returns_original_frame():
    frame = np.full((40, 60, 3), 30, np.uint8)
    assert FrameEnhancer(RuntimeSettings(camera_clahe_enabled=False)).apply(frame) is frame


def test_clahe_changes_only_lab_luminance_and_preserves_rgb(monkeypatch):
    frame = np.zeros((64, 64, 3), np.uint8)
    frame[:, :32] = (90, 10, 5)
    frame[:, 32:] = (90, 85, 5)
    original = frame.copy()
    lab = cv2.cvtColor(frame, cv2.COLOR_RGB2LAB)
    expected = lab.copy()
    expected[:, :, 0] = cv2.createCLAHE(3.0, (8, 8)).apply(lab[:, :, 0])
    real_cvt_color = cv2.cvtColor
    converted = []

    def convert(image, code):
        if code == cv2.COLOR_LAB2RGB:
            converted.append(image.copy())
        return real_cvt_color(image, code)

    monkeypatch.setattr(cv2, "cvtColor", convert)
    result = FrameEnhancer(_settings()).apply(frame)
    np.testing.assert_array_equal(converted[0][:, :, 1:], lab[:, :, 1:])
    np.testing.assert_array_equal(result, real_cvt_color(expected, cv2.COLOR_LAB2RGB))
    np.testing.assert_array_equal(frame, original)
    assert result.dtype == np.uint8
    assert result.shape == frame.shape
    assert result[32, 16, 0] > result[32, 16, 2]
    assert result[32, 48, 0] > result[32, 48, 2]


def test_clahe_reused_across_frames(monkeypatch):
    real_create = cv2.createCLAHE
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return real_create(**kwargs)

    monkeypatch.setattr(cv2, "createCLAHE", create)
    enhancer = FrameEnhancer(_settings(camera_clahe_clip_limit=2.0))
    for _ in range(3):
        enhancer.apply(np.zeros((64, 64, 3), np.uint8))
    assert calls == [{"clipLimit": 2.0, "tileGridSize": (8, 8)}]


def test_dark_foreground_luminance_improves():
    gradient = np.tile(np.linspace(20, 60, 640, dtype=np.uint8), (480, 1))
    frame = np.repeat(gradient[:, :, None], 3, axis=2)
    frame[:, 480:] = 240
    result = FrameEnhancer(_settings()).apply(frame)
    before = cv2.cvtColor(frame, cv2.COLOR_RGB2LAB)[:, :400, 0].mean()
    after = cv2.cvtColor(result, cv2.COLOR_RGB2LAB)[:, :400, 0].mean()
    assert after > before + 5


@pytest.mark.parametrize("color", ["red", "yellow"])
@pytest.mark.parametrize("level", [78, 255])
def test_runtime_detects_backlit_and_normal_balls(monkeypatch, color, level):
    frame = np.full((480, 640, 3), 240, np.uint8)
    cv2.circle(frame, (320, 240), 25, (level, 0, 0) if color == "red" else (level, level, 0), -1)
    monkeypatch.setattr(
        camera_live_perception_pipeline, "load_runtime_settings",
        lambda: RuntimeSettings(camera_clahe_enabled=False, camera_exposure_value=0.0),
    )
    uncorrected = camera_live_perception_pipeline.CameraLivePerceptionPipeline(autostart=False)
    baseline = uncorrected._process_frame(frame, target=camera_target(uncorrected, color))
    if level < 80:
        assert baseline is None
    monkeypatch.setattr(camera_live_perception_pipeline, "load_runtime_settings", _settings)
    corrected = camera_live_perception_pipeline.CameraLivePerceptionPipeline(autostart=False)
    detection = corrected._process_frame(frame, target=camera_target(corrected, color))
    assert detection is not None
    assert detection.label == f"{color}_ball"
    assert detection.diameter_px == pytest.approx(49, abs=1)
    if baseline is not None:
        assert detection.position == baseline.position
        assert detection.distance_cm == pytest.approx(baseline.distance_cm)


@pytest.mark.parametrize("foreground,background", [(0, 255), (15, 90)])
def test_runtime_detects_same_aruco_id_after_enhancement(monkeypatch, foreground, background):
    marker = cv2.aruco.generateImageMarker(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), 1, 80,
    )
    marker = np.where(marker == 0, foreground, background).astype(np.uint8)
    image = np.full((640, 480), background, np.uint8)
    image[280:360, 200:280] = marker
    frame = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    monkeypatch.setattr(
        camera_live_perception_pipeline, "load_runtime_settings",
        lambda: RuntimeSettings(camera_clahe_enabled=False, camera_exposure_value=0.0),
    )
    baseline_pipeline = camera_live_perception_pipeline.CameraLivePerceptionPipeline(autostart=False)
    baseline = baseline_pipeline._process_frame(
        frame, target=camera_target(baseline_pipeline, "marker")
    )
    monkeypatch.setattr(camera_live_perception_pipeline, "load_runtime_settings", _settings)
    corrected = camera_live_perception_pipeline.CameraLivePerceptionPipeline(autostart=False)
    detection = corrected._process_frame(frame, target=camera_target(corrected, "marker"))
    assert detection is not None and baseline is not None
    assert detection.label == baseline.label == "marker_1"
    assert detection.position == baseline.position
    assert detection.distance_cm == pytest.approx(baseline.distance_cm, rel=0.01)


@pytest.mark.parametrize("level", [0, 30, 128, 255])
@pytest.mark.parametrize("target", ["red", "yellow", "marker"])
def test_uniform_frames_do_not_create_detections(monkeypatch, level, target):
    monkeypatch.setattr(camera_live_perception_pipeline, "load_runtime_settings", _settings)
    pipeline = camera_live_perception_pipeline.CameraLivePerceptionPipeline(autostart=False)
    assert pipeline._process_frame(
        np.full((480, 640, 3), level, np.uint8),
        target=camera_target(pipeline, target),
    ) is None


def test_exposure_applied_to_supported_camera():
    calls = []
    camera = SimpleNamespace(camera_controls={"ExposureValue": (-8, 8, 0)}, set_controls=calls.append)
    configure_exposure(camera, _settings(camera_exposure_value=1.0))
    assert calls == [{"ExposureValue": 1.0}]


def test_zero_exposure_leaves_camera_untouched():
    configure_exposure(SimpleNamespace(), RuntimeSettings(camera_exposure_value=0.0))


def test_unsupported_exposure_is_logged(caplog):
    camera = SimpleNamespace(camera_controls={}, set_controls=lambda controls: pytest.fail("unsupported"))
    configure_exposure(camera, _settings(camera_exposure_value=1.0))
    assert "ExposureValue non pris en charge" in caplog.text


def test_exposure_failure_is_not_silenced():
    def fail(controls):
        raise RuntimeError("exposure rejected")

    camera = SimpleNamespace(camera_controls={"ExposureValue": (-8, 8, 0)}, set_controls=fail)
    with pytest.raises(RuntimeError, match="exposure rejected"):
        configure_exposure(camera, _settings(camera_exposure_value=1.0))
