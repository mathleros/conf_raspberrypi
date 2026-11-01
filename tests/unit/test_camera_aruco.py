import queue
import math
import threading
import time

import cv2
import numpy as np
import pytest

from irobot.config.settings import MarkerIdentity, RuntimeSettings
from irobot.hardware.camera import camera_live_pipeline

from irobot.interfaces.aruco_marker_decoder import ArucoFrameDetection, ObservationDisposition
from irobot.interfaces.robot_controller import RobotController
from irobot.interfaces.voice_runtime import VoiceRuntime
from tests.unit.fake_robot import FakeRobot

def _frame(center_x=240, width=80, image_width=480, marker_id=1):
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, width)
    grayscale = np.full((640, image_width), 255, dtype=np.uint8)
    left = center_x - width // 2
    grayscale[280:280 + width, left:left + width] = marker
    return cv2.cvtColor(grayscale, cv2.COLOR_GRAY2RGB)


@pytest.fixture
def pipeline(monkeypatch):
    monkeypatch.setattr(camera_live_pipeline, "load_runtime_settings", RuntimeSettings)
    return camera_live_pipeline.CameraLivePerceptionPipeline(
        default_target="marker", autostart=False,
    )


@pytest.mark.parametrize(
    ("center_x", "position"),
    [(179, "left"), (181, "center"), (240, "center"), (300, "center"), (301, "right")],
)
def test_marker_position_and_distance(pipeline, center_x, position):
    detection = pipeline._process_frame(_frame(center_x))
    assert detection.label == "marker_1"
    assert detection.position == position
    assert detection.confidence == 1.0
    assert detection.distance_cm == pytest.approx(
        8 / 79 * math.sqrt(600**2 + (center_x - 240.5)**2 + 0.5**2),
    )
    pipeline._last_detection = detection
    assert pipeline.detect(target="me").distance_cm == detection.distance_cm


def test_position_scales_to_image_width(pipeline):
    assert pipeline._process_frame(_frame(center_x=440, image_width=640)).position == "right"


@pytest.mark.parametrize(
    ("center_x", "position"),
    [(179, "left"), (180, "center"), (300, "center"), (301, "right")],
)
def test_exact_thresholds_and_grayscale_input(pipeline, monkeypatch, center_x, position):
    frame = _frame()

    def detect(grayscale):
        np.testing.assert_array_equal(grayscale, cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY))
        return ArucoFrameDetection(
            ObservationDisposition.VALID,
            corners_px=(
                (center_x - 40, 280), (center_x + 40, 280),
                (center_x + 40, 360), (center_x - 40, 360),
            ),
        )

    monkeypatch.setattr(pipeline._marker_decoder, "detect", detect)
    detection = pipeline._process_frame(frame)
    assert detection.position == position
    assert detection.distance_cm == pytest.approx(
        8 / 80 * math.hypot(600, center_x - 240),
    )


def test_configured_identity(monkeypatch):
    identity = MarkerIdentity("aruco", "DICT_4X4_50", "2")
    monkeypatch.setattr(
        camera_live_pipeline, "load_runtime_settings",
        lambda: RuntimeSettings(human_marker_identity=identity),
    )
    pipeline = camera_live_pipeline.CameraLivePerceptionPipeline(
        default_target="marker", autostart=False,
    )
    assert pipeline._marker_decoder.identity == identity
    assert pipeline._process_frame(_frame(marker_id=1)) is None
    assert pipeline._process_frame(_frame(marker_id=2)).label == "marker_1"


@pytest.mark.parametrize("target", ["marker", "me"])
def test_requested_target_changes_camera_processing(pipeline, target):
    pipeline.default_target = "red"
    assert pipeline.detect(target=target) is None
    detection = pipeline._process_frame(_frame())
    pipeline._last_detection = detection
    assert pipeline.detect(target=target).label == "marker_1"
    assert pipeline.detect(target="red") is None
    assert pipeline._process_frame(_frame()) is None


def test_marker_precedes_colors_without_ball_filter(pipeline):
    pipeline.default_target = ""
    frame = _frame()
    cv2.circle(frame, (400, 150), 25, (255, 0, 0), -1)
    assert pipeline._process_frame(frame).label == "marker_1"
    pipeline.default_target = "red"
    assert pipeline._process_frame(frame).label == "red_ball"


@pytest.mark.parametrize("disposition", [
    ObservationDisposition.ABSENT, ObservationDisposition.REJECTED,
    ObservationDisposition.AMBIGUOUS, ObservationDisposition.FAULT,
])
def test_nonvalid_marker_is_not_returned(pipeline, monkeypatch, disposition):
    monkeypatch.setattr(
        pipeline._marker_decoder, "detect",
        lambda image: ArucoFrameDetection(disposition),
    )
    assert pipeline._process_frame(_frame()) is None


def test_degenerate_marker_is_logged(pipeline, monkeypatch, caplog):
    monkeypatch.setattr(
        pipeline._marker_decoder, "detect",
        lambda image: ArucoFrameDetection(
            ObservationDisposition.VALID, corners_px=((240.0, 300.0),) * 4,
        ),
    )
    assert pipeline._process_frame(_frame()) is None
    assert "Pose ArUco inexploitable" in caplog.text


def test_marker_distance_is_not_fused_with_ultrasound(pipeline):
    pipeline.fusion_enabled = True

    def unexpected_read():
        pytest.fail("Marker distance must remain the pose estimate")

    pipeline.distance_reader = unexpected_read
    pipeline._last_detection = pipeline._process_frame(_frame())
    assert pipeline.detect(target="marker").distance_cm == pytest.approx(
        8 / 79 * math.sqrt(600**2 + 0.5**2 + 0.5**2),
    )


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

    monkeypatch.setattr(camera_live_pipeline, "Picamera2", Camera)
    monkeypatch.setattr(camera_live_pipeline, "load_runtime_settings", RuntimeSettings)
    pipeline = camera_live_pipeline.CameraLivePerceptionPipeline(poll_interval_s=0)
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


@pytest.mark.parametrize("target", ["marker", "me"])
def test_live_target_switch_waits_for_matching_frame(live_pipeline, target):
    pipeline, frames, second_capture, wait_started = live_pipeline
    results = []
    reader = threading.Thread(target=lambda: results.append(pipeline.detect(target=target)))
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


@pytest.mark.parametrize("phrase", ["suis-moi", "approche toi de moi"])
def test_voice_follow_waits_for_marker_without_motion(live_pipeline, tmp_path, monkeypatch, phrase):
    pipeline, frames, second_capture, wait_started = live_pipeline
    robot = FakeRobot()
    close_seen = threading.Event()
    holding = threading.Event()
    original_detect = pipeline.detect
    original_stop = robot.stop

    def detect(*, target=None):
        detection = original_detect(target=target)
        if detection is not None and detection.distance_cm <= 30:
            close_seen.set()
        return detection

    def stop():
        original_stop()
        if close_seen.is_set():
            holding.set()

    monkeypatch.setattr(pipeline, "detect", detect)
    monkeypatch.setattr(robot, "stop", stop)
    runtime = VoiceRuntime(
        robot=RobotController(robot), perception=pipeline, use_llm=False, trace_dir=str(tmp_path),
    )
    results = []
    reader = threading.Thread(target=lambda: results.append(runtime.handle_text_as_plan(phrase)))
    reader.start()
    try:
        assert wait_started.wait(2)
        assert robot.commands == []
        frames.put(_frame())
        assert second_capture.wait(2)
        assert reader.is_alive()
        # Un marqueur plus grand est dans le seuil d'approche commun, sans exception ArUco.
        frames.put(_frame(width=200))
        assert holding.wait(2)
        assert set(robot.commands) == {"stop"}
        if phrase == "suis-moi":
            assert reader.is_alive()
            assert results == []
            runtime.handle_transcript("stop")
        reader.join(2)
        assert not reader.is_alive()
        step = results[0]["steps"][0]
        assert step["attempt"] == 1
        if phrase == "suis-moi":
            assert results[0]["status"] == "aborted"
            assert step["reason"] == "emergency stop"
            assert step["plan"] == ["follow_object"]
            skill_result = step["results"][0]
            assert skill_result.data["emergency_stop"] is True
            distance_cm = skill_result.data["final_distance_cm"]
        else:
            assert results[0]["status"] == "accepted"
            skill_result = step["results"][step["plan"].index("approach_target")]
            assert skill_result.data["close_enough"] is True
            distance_cm = skill_result.data["distance_cm"]
        assert distance_cm == pytest.approx(
            8 / 199 * math.sqrt(600**2 + 0.5**2 + 59.5**2),
        )
        assert set(robot.commands) == {"stop"}
    finally:
        runtime._request_emergency_stop()
        with pipeline._frame_condition:
            pipeline._stop_event.set()
            pipeline._frame_condition.notify_all()
        reader.join(2)


def test_target_frame_wait_is_bounded_and_logged(live_pipeline, caplog, monkeypatch):
    pipeline, _, _, _ = live_pipeline
    monkeypatch.setattr(pipeline, "TARGET_FRAME_TIMEOUT_S", 0.03)
    started = time.monotonic()
    assert pipeline.detect(target="marker") is None
    elapsed = time.monotonic() - started
    assert 0.025 <= elapsed < 0.5
    assert "Délai dépassé" in caplog.text


@pytest.mark.parametrize("present", [False, True])
def test_matching_frame_is_cached_including_absence(live_pipeline, present, monkeypatch):
    pipeline, frames, second_capture, wait_started = live_pipeline
    results = []
    reader = threading.Thread(target=lambda: results.append(pipeline.detect(target="marker")))
    reader.start()
    try:
        assert wait_started.wait(2)
        frames.put(_frame())
        assert second_capture.wait(2)
        frames.put(_frame() if present else np.full((640, 480, 3), 255, np.uint8))
        reader.join(2)
        assert not reader.is_alive()
        monkeypatch.setattr(pipeline, "TARGET_FRAME_TIMEOUT_S", 0)
        cached = pipeline.detect(target="me")
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
    reader = threading.Thread(target=lambda: results.append(pipeline.detect(target="marker")))
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
