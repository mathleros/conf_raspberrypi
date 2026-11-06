import queue
import math
import threading
import time
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from irobot.common.config.settings import MarkerIdentity, RuntimeSettings
from irobot.common.hardware.camera import camera_live_perception_pipeline

from irobot.common.hardware.camera.detector import ArucoFrameDetection, ObservationDisposition
from irobot.common.interfaces.robot_controller import RobotController
from irobot.app.interfaces.voice_runtime import VoiceRuntime
from tests.unit.fake_robot import FakeRobot
from tests.unit.perception_helpers import camera_target


def _frame(center_x=240, width=80, image_width=480, marker_id=1):
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, width)
    grayscale = np.full((640, image_width), 255, dtype=np.uint8)
    left = center_x - width // 2
    grayscale[280:280 + width, left:left + width] = marker
    return cv2.cvtColor(grayscale, cv2.COLOR_GRAY2RGB)


def _runtime_settings(**kwargs):
    return RuntimeSettings(
        camera_focal_px=600.0,
        camera_clahe_enabled=False,
        camera_exposure_value=0.0,
        **kwargs,
    )


@pytest.fixture
def pipeline(monkeypatch):
    monkeypatch.setattr(camera_live_perception_pipeline, "load_runtime_settings", _runtime_settings)
    return camera_live_perception_pipeline.CameraLivePerceptionPipeline(
        autostart=False,
    )


@pytest.mark.parametrize(
    ("center_x", "position"),
    [(179, "left"), (181, "center"), (240, "center"), (300, "center"), (301, "right")],
)
def test_marker_position_and_distance(pipeline, center_x, position):
    strategy = camera_target(pipeline, "marker")
    pipeline.detect(target=strategy)
    detection = pipeline._process_frame(_frame(center_x), target=strategy)
    assert detection.label == "marker_1"
    assert detection.position == position
    assert detection.confidence == 1.0
    assert detection.distance_cm == pytest.approx(
        8 / 79 * math.sqrt(600**2 + (center_x - 240.5)**2 + 0.5**2),
    )
    pipeline._last_detection = detection
    assert pipeline.detect(target=camera_target(pipeline, "tag")).distance_cm == detection.distance_cm


def test_position_scales_to_image_width(pipeline):
    assert pipeline._process_frame(
        _frame(center_x=440, image_width=640), target=camera_target(pipeline, "marker")
    ).position == "right"


@pytest.mark.parametrize(
    ("center_x", "position"),
    [(179, "left"), (180, "center"), (300, "center"), (301, "right")],
)
def test_exact_thresholds_and_grayscale_input(pipeline, monkeypatch, center_x, position):
    frame = _frame()

    def detect_markers(grayscale):
        np.testing.assert_array_equal(grayscale, cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY))
        corners = np.asarray([[
                (center_x - 40, 280), (center_x + 40, 280),
                (center_x + 40, 360), (center_x - 40, 360),
            ]], dtype=np.float32)
        return corners, np.asarray([[1]], dtype=np.int32), None

    monkeypatch.setattr(
        pipeline._detector._marker_detector,
        "_detector",
        SimpleNamespace(detectMarkers=detect_markers),
    )
    detection = pipeline._process_frame(frame, target=camera_target(pipeline, "marker"))
    assert detection.position == position
    assert detection.distance_cm == pytest.approx(
        8 / 80 * math.hypot(600, center_x - 240),
    )


def test_configured_identity(monkeypatch):
    identity = MarkerIdentity("aruco", "DICT_4X4_50", "2")
    monkeypatch.setattr(
        camera_live_perception_pipeline, "load_runtime_settings",
        lambda: _runtime_settings(human_marker_identity=identity),
    )
    pipeline = camera_live_perception_pipeline.CameraLivePerceptionPipeline(
        autostart=False,
    )
    marker_detector = pipeline._detector._marker_detector
    assert marker_detector.identity == identity
    assert pipeline._process_frame(_frame(marker_id=1), target=camera_target(pipeline, "marker")) is None
    assert pipeline._process_frame(
        _frame(marker_id=2), target=camera_target(pipeline, "marker")
    ).label == "marker_1"


def test_detect_returns_complete_marker_result(pipeline):
    detector = pipeline._detector._marker_detector

    assert detector.focal_px == pipeline.focal_px == 600.0
    detected = detector.detect(_frame())
    assert detected.disposition is ObservationDisposition.VALID
    assert detected.corners_px is not None
    assert detected.distance_cm is not None
    assert detected.bbox_px is not None
    object_detection = detected.as_object_detection()
    assert object_detection is not None
    assert object_detection.distance_cm == detected.distance_cm

    absent = detector.detect(np.full((640, 480, 3), 255, dtype=np.uint8))
    assert absent.disposition is ObservationDisposition.ABSENT
    assert absent.corners_px is None
    assert absent.distance_cm is None
    assert absent.as_object_detection() is None


@pytest.mark.parametrize("target", ["marker", "tag"])
def test_requested_target_changes_camera_processing(pipeline, target):
    strategy = camera_target(pipeline, target)
    assert pipeline.detect(target=strategy) is None
    detection = pipeline._process_frame(_frame(), target=strategy)
    pipeline._last_detection = detection
    assert pipeline.detect(target=strategy).label == "marker_1"
    red_strategy = camera_target(pipeline, "red")
    assert pipeline.detect(target=red_strategy) is None
    assert pipeline._process_frame(_frame(), target=red_strategy) is None


def test_marker_and_color_targets_use_only_the_requested_detector(pipeline):
    frame = _frame()
    cv2.circle(frame, (400, 150), 25, (255, 0, 0), -1)
    assert pipeline._process_frame(frame, target=camera_target(pipeline, "marker")).label == "marker_1"
    assert pipeline._process_frame(frame, target=camera_target(pipeline, "red")).label == "red_ball"


def test_missing_strategy_is_not_silently_defaulted(pipeline):
    with pytest.raises(TypeError):
        pipeline.detect()
    assert pipeline._requested_target is None


@pytest.mark.parametrize("disposition", [
    ObservationDisposition.ABSENT, ObservationDisposition.REJECTED,
    ObservationDisposition.AMBIGUOUS, ObservationDisposition.FAULT,
])
def test_nonvalid_marker_is_not_returned(pipeline, monkeypatch, disposition):
    monkeypatch.setattr(
        pipeline._detector._marker_detector, "detect",
        lambda image: ArucoFrameDetection(disposition),
    )
    assert pipeline._process_frame(_frame(), target=camera_target(pipeline, "marker")) is None


def test_degenerate_marker_is_logged(pipeline, monkeypatch, caplog):
    marker_detector = pipeline._detector._marker_detector
    monkeypatch.setattr(
        marker_detector,
        "_detector",
        SimpleNamespace(detectMarkers=lambda image: (
            [[(240.0, 300.0)] * 4], [[marker_detector.expected_id]], None,
        )),
    )
    assert pipeline._process_frame(_frame(), target=camera_target(pipeline, "marker")) is None
    assert "Pose ArUco inexploitable" in caplog.text


@pytest.fixture
def live_pipeline(monkeypatch):
    frames = queue.Queue()
    first_capture = threading.Event()
    second_capture = threading.Event()
    wait_started = threading.Event()

    class Camera:
        captures = 0

        def __init__(self, index):
            pass

        def create_preview_configuration(self, **kwargs):
            return kwargs

        def configure(self, config):
            pass

        def start(self):
            pass

        def capture_array(self):
            self.captures += 1
            (first_capture if self.captures == 1 else second_capture).set()
            frame = frames.get(timeout=3)
            if isinstance(frame, Exception):
                raise frame
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        def stop(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(camera_live_perception_pipeline, "Picamera2", Camera)
    monkeypatch.setattr(camera_live_perception_pipeline, "load_runtime_settings", _runtime_settings)
    pipeline = camera_live_perception_pipeline.CameraLivePerceptionPipeline(poll_interval_s=0)
    original_wait = pipeline._frame_condition.wait_for

    def wait_for(predicate, timeout=None):
        wait_started.set()
        return original_wait(predicate, timeout)

    monkeypatch.setattr(pipeline._frame_condition, "wait_for", wait_for)
    try:
        assert first_capture.wait(2)
        yield pipeline, frames, second_capture, wait_started
    finally:
        pipeline._stop_event.set()
        frames.put(_frame())
        pipeline.close()


@pytest.mark.parametrize("target", ["marker", "tag"])
def test_live_target_switch_waits_for_matching_frame(live_pipeline, target):
    pipeline, frames, second_capture, wait_started = live_pipeline
    results = []
    strategy = camera_target(pipeline, target)
    reader = threading.Thread(target=lambda: results.append(pipeline.detect(target=strategy)))
    reader.start()
    try:
        assert wait_started.wait(2)
        frames.put(_frame())
        assert second_capture.wait(2)
        assert reader.is_alive()
        assert results == []
        frames.put(_frame())
        reader.join(2)
        assert not reader.is_alive()
        assert results[0].label == "marker_1"
        assert results[0].distance_cm == pytest.approx(
            8 / 79 * math.sqrt(600**2 + 0.5**2 + 0.5**2),
        )
    finally:
        with pipeline._frame_condition:
            pipeline._stop_event.set()
            pipeline._frame_condition.notify_all()
        reader.join(2)


def test_target_frame_wait_is_bounded_and_logged(live_pipeline, caplog, monkeypatch):
    pipeline, _, _, _ = live_pipeline
    monkeypatch.setattr(pipeline, "TARGET_FRAME_TIMEOUT_S", 0.03)
    started = time.monotonic()
    assert pipeline.detect(target=camera_target(pipeline, "marker")) is None
    elapsed = time.monotonic() - started
    assert 0.025 <= elapsed < 0.5
    assert "Délai dépassé" in caplog.text


@pytest.mark.parametrize("present", [False, True])
def test_matching_frame_is_cached_including_absence(live_pipeline, present, monkeypatch):
    pipeline, frames, second_capture, wait_started = live_pipeline
    results = []
    strategy = camera_target(pipeline, "marker")
    reader = threading.Thread(target=lambda: results.append(pipeline.detect(target=strategy)))
    reader.start()
    try:
        assert wait_started.wait(2)
        frames.put(_frame())
        assert second_capture.wait(2)
        frames.put(_frame() if present else np.full((640, 480, 3), 255, np.uint8))
        reader.join(2)
        assert not reader.is_alive()
        monkeypatch.setattr(pipeline, "TARGET_FRAME_TIMEOUT_S", 0)
        cached = pipeline.detect(target=camera_target(pipeline, "tag"))
        assert (cached is not None) == present
        assert (results[0] is not None) == present
        assert pipeline._frame_revision == pipeline._target_revision
    finally:
        with pipeline._frame_condition:
            pipeline._stop_event.set()
            pipeline._frame_condition.notify_all()
        reader.join(2)


@pytest.mark.parametrize("failure", [False, True])
def test_target_frame_wait_is_released_on_close_or_failure(live_pipeline, failure, caplog):
    pipeline, frames, _, wait_started = live_pipeline
    results = []
    strategy = camera_target(pipeline, "marker")
    reader = threading.Thread(target=lambda: results.append(pipeline.detect(target=strategy)))
    reader.start()
    try:
        assert wait_started.wait(2)
        if failure:
            frames.put(RuntimeError("capture interrompue"))
        else:
            with pytest.raises(TimeoutError):
                pipeline.close(timeout_s=0)
        reader.join(0.5)
        assert not reader.is_alive()
        assert results == [None]
        if failure:
            assert "capture interrompue" in caplog.text
    finally:
        with pipeline._frame_condition:
            pipeline._stop_event.set()
            pipeline._frame_condition.notify_all()
        reader.join(2)
