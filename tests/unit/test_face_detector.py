from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from irobot.config.settings import RuntimeSettings
from irobot.domain.skills.base_skill import SkillContext
from irobot.domain.skills.behaviors.follow_object import FollowObjectSkill
from irobot.hardware.camera import camera_live_pipeline
from irobot.hardware.camera.detector import FaceDetector
from irobot.hardware.camera.frame_enhancer import FrameEnhancer
from irobot.interfaces.perception_pipeline import ObjectDetection, ObjectPerceptionPipeline
from tests.unit.fake_robot import FakeRobot


def _faces(*boxes):
    return np.array([(*box[:4], *([0.0] * 10), box[4]) for box in boxes], dtype=np.float32)


@pytest.fixture
def yunet(tmp_path, monkeypatch):
    model = tmp_path / "model.onnx"
    model.touch()
    settings = RuntimeSettings(
        camera_face_model_path=str(model),
        camera_face_grace_frames=2,
        camera_focal_px=600.0,
        camera_clahe_enabled=False,
        camera_exposure_value=0.0,
    )

    class Net:
        faces = None
        inputs = []
        sizes = []
        creates = []

        def setInputSize(self, size):
            self.sizes.append(size)

        def detect(self, frame):
            self.inputs.append(frame.copy())
            if isinstance(self.faces, Exception):
                raise self.faces
            return 1, self.faces

    net = Net()

    def create(*args, **kwargs):
        net.creates.append((args, kwargs))
        return net

    monkeypatch.setattr(cv2, "FaceDetectorYN", SimpleNamespace(create=create))
    return settings, net


def test_yunet_configuration_and_rgb_input(yunet):
    settings, net = yunet
    detector = FaceDetector(settings)
    frame = np.full((640, 480, 3), (120, 10, 5), np.uint8)
    assert detector.detect(frame) is None
    assert net.creates == [(
        (settings.camera_face_model_path, "", (300, 300)),
        {"score_threshold": 0.45, "nms_threshold": 0.3, "top_k": 5000},
    )]
    assert net.sizes == [(480, 640)]
    np.testing.assert_array_equal(net.inputs[0], cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))


def test_largest_eligible_face_and_distance(yunet):
    settings, net = yunet
    net.faces = _faces(
        (10, 20, 50, 80, 0.99),
        (180, 20, 100, 110, 0.75),
        (10, 20, 300, 300, 0.2),
    )
    detection = FaceDetector(settings).detect(np.zeros((640, 480, 3), np.uint8))
    assert detection.label == "face"
    assert detection.position == "center"
    assert detection.confidence == pytest.approx(0.75)
    assert detection.diameter_px == 100
    assert detection.distance_cm == 90
    assert detection.distance_visual_cm == 90


@pytest.mark.parametrize("center,position", [
    (179, "left"), (180, "center"), (300, "center"), (301, "right"),
])
@pytest.mark.parametrize("scale", [1, 2])
def test_position_thresholds_scale_with_frame_width(yunet, center, position, scale):
    settings, net = yunet
    net.faces = _faces(((center - 40) * scale, 20, 80 * scale, 80, 0.9))
    detection = FaceDetector(settings, focal_px=600 * scale).detect(
        np.zeros((640, 480 * scale, 3), np.uint8),
    )
    assert detection.position == position
    assert detection.distance_cm == pytest.approx(112.5)


def test_custom_face_width_focal_and_score_threshold(yunet):
    settings, net = yunet
    settings = replace(settings, camera_face_width_cm=12, camera_face_score_threshold=0.8)
    net.faces = _faces((10, 20, 60, 80, 0.8), (150, 20, 100, 100, 0.79))
    detection = FaceDetector(settings, focal_px=500).detect(np.zeros((640, 480, 3), np.uint8))
    assert detection.diameter_px == 60
    assert detection.distance_cm == 100


def test_grace_expires_after_exactly_n_missing_frames(yunet):
    settings, net = yunet
    detector = FaceDetector(settings)
    frame = np.zeros((640, 480, 3), np.uint8)
    assert detector.detect(frame) is None
    net.faces = _faces((180, 20, 100, 100, 0.9))
    first = detector.detect(frame)
    assert detector.bounding_box == (180, 20, 100, 100)
    assert detector.is_cached is False
    net.faces = None
    assert detector.detect(frame) == first
    assert detector.bounding_box == (180, 20, 100, 100)
    assert detector.is_cached is True
    assert detector.detect(frame) == first
    assert detector.detect(frame) is None
    assert detector.bounding_box is None
    assert detector.is_cached is False
    assert detector.detect(frame) is None


def test_low_scores_and_empty_arrays_consume_grace(yunet):
    settings, net = yunet
    detector = FaceDetector(settings)
    frame = np.zeros((640, 480, 3), np.uint8)
    net.faces = _faces((180, 20, 100, 100, 0.9))
    first = detector.detect(frame)
    net.faces = _faces((180, 20, 100, 100, 0.3))
    assert detector.detect(frame) == first
    net.faces = np.empty((0, 15), np.float32)
    assert detector.detect(frame) == first
    assert detector.detect(frame) is None


def test_reacquisition_restarts_grace_and_results_cannot_mutate_memory(yunet):
    settings, net = yunet
    detector = FaceDetector(settings)
    frame = np.zeros((640, 480, 3), np.uint8)
    net.faces = _faces((180, 20, 100, 100, 0.9))
    first = detector.detect(frame)
    first.distance_cm = -1
    net.faces = None
    assert detector.detect(frame).distance_cm == 90
    net.faces = _faces((10, 20, 50, 80, 0.95))
    second = detector.detect(frame)
    assert second.position == "left"
    assert second.distance_cm == 180
    net.faces = None
    assert detector.detect(frame) == second
    assert detector.detect(frame) == second
    assert detector.detect(frame) is None


@pytest.mark.parametrize("action", ["reset", "resize", "disabled"])
def test_grace_reset_resize_and_disabled(yunet, action):
    settings, net = yunet
    if action == "disabled":
        settings = replace(settings, camera_face_grace_frames=0)
    detector = FaceDetector(settings)
    frame = np.zeros((640, 480, 3), np.uint8)
    net.faces = _faces((180, 20, 100, 100, 0.9))
    assert detector.detect(frame) is not None
    net.faces = None
    if action == "reset":
        detector.reset()
    if action == "resize":
        frame = np.zeros((480, 640, 3), np.uint8)
    assert detector.detect(frame) is None


@pytest.mark.parametrize("bad_faces", [
    np.zeros((1, 14), np.float32),
    _faces((10, 20, 0, 80, 0.9)),
    _faces((10, 20, 80, -1, 0.9)),
    _faces((10, 20, 80, 80, float("nan"))),
    _faces((10, 20, 80, 80, 1.1)),
    cv2.error("synthetic inference failure"),
])
def test_faults_clear_memory_and_are_explicit(yunet, bad_faces, caplog):
    settings, net = yunet
    detector = FaceDetector(settings)
    frame = np.zeros((640, 480, 3), np.uint8)
    net.faces = _faces((180, 20, 100, 100, 0.9))
    assert detector.detect(frame) is not None
    net.faces = bad_faces
    with pytest.raises((ValueError, cv2.error)):
        detector.detect(frame)
    assert "mémoire du visage effacée" in caplog.text
    net.faces = None
    assert detector.detect(frame) is None


def test_missing_model_fails_explicitly(tmp_path):
    with pytest.raises(FileNotFoundError, match="YuNet introuvable"):
        FaceDetector(RuntimeSettings(camera_face_model_path=str(tmp_path / "missing.onnx")))


@pytest.fixture
def pipeline(yunet, monkeypatch):
    settings, net = yunet
    monkeypatch.setattr(
        camera_live_pipeline, "load_runtime_settings",
        lambda: replace(settings, camera_clahe_enabled=True),
    )
    return camera_live_pipeline.CameraLivePerceptionPipeline(autostart=False), net


@pytest.mark.parametrize("target", ["face", "human"])
def test_pipeline_face_routes_enhanced_frame_without_aruco_or_colors(pipeline, monkeypatch, target):
    camera, net = pipeline
    frame = np.full((640, 480, 3), (90, 10, 5), np.uint8)
    net.faces = _faces((180, 20, 100, 100, 0.9))
    monkeypatch.setattr(
        camera._marker_detector, "detect",
        lambda image: pytest.fail("No ArUco for faces"),
    )
    for detector in camera._color_detectors.values():
        monkeypatch.setattr(
            detector, "detect",
            lambda image: pytest.fail("No color detector for faces"),
        )
    assert camera.detect(target=target) is None
    detection = camera._process_frame(frame)
    camera._last_detection = detection
    camera.fusion_enabled = True
    camera.distance_reader = lambda: pytest.fail("No ultrasound for faces")
    assert camera.detect(target=target).label == "face"
    expected = FrameEnhancer(camera._settings).apply(frame)
    np.testing.assert_array_equal(net.inputs[-1], cv2.cvtColor(expected, cv2.COLOR_RGB2BGR))
    assert len(net.creates) == 1
    assert camera._process_frame(frame, target=target) is not None
    assert len(net.creates) == 1


def test_face_aliases_do_not_change_request_revision(pipeline):
    camera, net = pipeline
    frame = np.zeros((640, 480, 3), np.uint8)
    camera.detect(target="human")
    revision = camera._target_revision
    net.faces = _faces((180, 20, 100, 100, 0.9))
    camera._last_detection = camera._process_frame(frame)
    assert camera.detect(target="face").label == "face"
    assert camera._target_revision == revision
    net.faces = None
    assert camera.detect(target="face") is not None
    assert camera._process_frame(frame).label == "face"


def test_changing_to_balls_clears_face_memory(pipeline):
    camera, net = pipeline
    frame = np.zeros((640, 480, 3), np.uint8)
    net.faces = _faces((180, 20, 100, 100, 0.9))
    assert camera._process_frame(frame, target="face") is not None
    camera._process_frame(frame, target="red")
    net.faces = None
    assert camera._process_frame(frame, target="face") is None


def test_face_model_not_loaded_for_other_targets(pipeline):
    camera, net = pipeline
    frame = np.zeros((640, 480, 3), np.uint8)
    for target in ("red", "yellow", "marker", "me"):
        camera._process_frame(frame, target=target)
    assert net.creates == []


def test_inflight_frame_and_rapid_target_changes_do_not_restore_old_face(pipeline, monkeypatch):
    camera, net = pipeline
    camera.default_target = "face"
    captures = 0
    closed = []

    class Camera:
        def create_preview_configuration(self, **kwargs):
            return kwargs

        def configure(self, config):
            pass

        def start(self):
            pass

        def capture_array(self):
            nonlocal captures
            captures += 1
            if captures == 1:
                net.faces = _faces((180, 20, 100, 100, 0.9))
            else:
                net.faces = None
            if captures == 2:
                assert camera._last_detection.label == "face"
                assert camera.detect(target="red") is None
                assert camera.detect(target="face") is None
            if captures == 3:
                camera._stop_event.set()
            return np.zeros((480, 640, 3), np.uint8)

        def stop(self):
            closed.append("stop")

        def close(self):
            closed.append("close")

    monkeypatch.setattr(camera_live_pipeline, "Picamera2", lambda index: Camera())
    camera._capture_loop()
    assert captures == 3
    assert len(net.inputs) == 3
    assert camera._target_revision == 2
    assert camera._frame_revision == 2
    assert camera._last_detection is None
    assert closed == ["stop", "close"]


@pytest.mark.parametrize("target", ["face", "human"])
def test_follow_skill_aligns_approaches_and_holds_face_from_perception_mock(target):
    clock = [0.0]

    def sleep(seconds):
        clock[0] += seconds

    robot = FakeRobot()
    detections = iter((
        ObjectDetection(label="face", position="left", distance_cm=200, confidence=0.9),
        ObjectDetection(label="face", position="center", distance_cm=200, confidence=0.9),
        ObjectDetection(label="face", position="center", distance_cm=100, confidence=0.9),
    ))
    last_detection = ObjectDetection(label="face", position="center", distance_cm=100, confidence=0.9)
    perception = Mock(spec=ObjectPerceptionPipeline)
    perception.detect.side_effect = lambda **kwargs: next(detections, last_detection)
    context = SkillContext(robot=robot, perception=perception, state={
        "active_intent_parameters": {"target_object": target, "duration_s": 1},
    })
    skill = FollowObjectSkill(settings=RuntimeSettings(), time_fn=lambda: clock[0], sleep_fn=sleep)
    result = skill.execute(context)
    assert result.status == "success"
    assert robot.commands.index("left") < robot.commands.index("forward")
    assert "backward" not in robot.commands
    assert result.data["final_distance_cm"] == 100
    assert context.state["follow_target_state"]["phase"] == "holding"
    assert robot.commands[-1] == "stop"
