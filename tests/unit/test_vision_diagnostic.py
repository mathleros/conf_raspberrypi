import math
import sys
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from irobot.config.settings import MarkerIdentity, RuntimeSettings
from irobot.hardware.camera import camera_live_perception_pipeline
from irobot.hardware.camera.detector.aruco_detector import estimate_marker_distance_cm
from irobot.hardware.camera.frame_enhancer import FrameEnhancer
from irobot.interfaces.perception_contracts import ObjectDetection
from irobot.tools.vision_diagnostic import detect_balls, format_object_status
from irobot.hardware.camera.detector import ArucoFrameDetection, ObservationDisposition
from irobot.tools.vision_diagnostic import (
    TEST_MARKER_IDENTITY,
    _draw_detection,
    format_detection_status,
)


def _project_marker(
    translation,
    yaw=0,
    pitch=0,
    roll=0,
    size=RuntimeSettings().camera_oriented_frame_size_px,
    focal_px=RuntimeSettings().camera_focal_px,
):
    # Independently project the physical square through a pinhole camera.
    y, p, r = map(math.radians, (yaw, pitch, roll))
    rotate_y = np.array(((math.cos(y), 0, math.sin(y)), (0, 1, 0),
                         (-math.sin(y), 0, math.cos(y))))
    rotate_x = np.array(((1, 0, 0), (0, math.cos(p), -math.sin(p)),
                         (0, math.sin(p), math.cos(p))))
    rotate_z = np.array(((math.cos(r), -math.sin(r), 0),
                         (math.sin(r), math.cos(r), 0), (0, 0, 1)))
    square = np.array(((-4, -4, 0), (4, -4, 0), (4, 4, 0), (-4, 4, 0)))
    points = square @ (rotate_z @ rotate_y @ rotate_x).T + translation
    width, height = size
    image_points = points[:, :2] / points[:, 2, None]
    image_points *= (
        focal_px * width / RuntimeSettings().camera_oriented_frame_size_px[0],
        focal_px * height / RuntimeSettings().camera_oriented_frame_size_px[1],
    )
    image_points += (width / 2, height / 2)
    corners = tuple((float(x), float(y)) for x, y in image_points)
    return ArucoFrameDetection(
        ObservationDisposition.VALID, TEST_MARKER_IDENTITY,
        corners,
        distance_cm=estimate_marker_distance_cm(corners, focal_px, size),
    )


@pytest.fixture
def runtime_pipeline(monkeypatch):
    monkeypatch.setattr(camera_live_perception_pipeline, "load_runtime_settings", RuntimeSettings)
    return camera_live_perception_pipeline.CameraLivePerceptionPipeline(
        autostart=False,
    )


def _patch_marker_corners(monkeypatch, detector, corners):
    marker_id = detector.expected_id
    backend = SimpleNamespace(
        detectMarkers=lambda image: ([list(corners)], [[marker_id]], None),
    )
    monkeypatch.setattr(detector, "_detector", backend)


@pytest.mark.parametrize("x", [-20, 0, 20])
@pytest.mark.parametrize("yaw", [-45, 0, 45])
@pytest.mark.parametrize("pitch,roll", [(0, 0), (25, 30)])
def test_distance_accounts_for_position_and_orientation(x, yaw, pitch, roll):
    translation = (x, 0, 80)
    detection = _project_marker(translation, yaw, pitch, roll)
    assert detection.distance_cm == pytest.approx(
        math.dist((0, 0, 0), translation), abs=0.01,
    )


def test_centered_frontal_distance_preserves_previous_result():
    detection = _project_marker((0, 0, 100))
    assert detection.distance_cm == pytest.approx(100, abs=0.01)
    assert "distance=100.0 cm" in format_detection_status(detection)


def test_tilted_off_axis_distance_is_not_based_on_width_only():
    detection = _project_marker((20, 0, 80), yaw=-30)
    corners = detection.corners_px
    width = (math.dist(corners[0], corners[1]) + math.dist(corners[3], corners[2])) / 2
    expected = math.hypot(20, 80)
    assert abs(4800 / width - expected) > 5
    assert detection.distance_cm == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize("x", [-20, 20])
def test_84_cm_off_axis_with_subpixel_corner_noise(x):
    detection = _project_marker((x, 0, math.sqrt(84**2 - x**2)), yaw=-30)
    noise = ((0.1, -0.2), (-0.1, 0.2), (0.2, 0.1), (-0.2, -0.1))
    noisy_corners = tuple(
        (x + dx, y + dy) for (x, y), (dx, dy) in zip(detection.corners_px, noise)
    )
    noisy_detection = ArucoFrameDetection(
        ObservationDisposition.VALID,
        TEST_MARKER_IDENTITY,
        noisy_corners,
        distance_cm=estimate_marker_distance_cm(
            noisy_corners, RuntimeSettings().camera_focal_px,
        ),
    )
    assert noisy_detection.distance_cm == pytest.approx(84, abs=1)


@pytest.mark.parametrize("size", [RuntimeSettings().camera_oriented_frame_size_px, (960, 1280)])
def test_distance_uses_actual_frame_dimensions(size):
    detection = _project_marker((20, 10, 80), yaw=30, size=size)
    assert detection.distance_cm == pytest.approx(
        math.sqrt(20**2 + 10**2 + 80**2), abs=0.01,
    )


@pytest.mark.parametrize("x,yaw", [(-20, -30), (0, 0), (20, 45)])
@pytest.mark.parametrize("size", [RuntimeSettings().camera_oriented_frame_size_px, (960, 1280)])
@pytest.mark.parametrize("target", ["marker", "me"])
@pytest.mark.parametrize("identifier", ["1", "2"])
def test_runtime_uses_pose_distance_for_configured_marker(
    runtime_pipeline, monkeypatch, x, yaw, size, target, identifier,
):
    projected = _project_marker((x, 10, 80), yaw=yaw, pitch=20, size=size)
    detection = ArucoFrameDetection(
        ObservationDisposition.VALID,
        MarkerIdentity("aruco", "DICT_4X4_50", identifier), projected.corners_px,
        distance_cm=projected.distance_cm,
    )
    marker_detector = runtime_pipeline._frame_processor._marker_detector
    monkeypatch.setattr(marker_detector, "identity", detection.identity)
    monkeypatch.setattr(marker_detector, "expected_id", int(identifier))
    _patch_marker_corners(monkeypatch, marker_detector, projected.corners_px)
    frame = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    runtime_pipeline.detect(target=target)
    result = runtime_pipeline._process_frame(frame, target=target)
    expected = math.sqrt(x**2 + 10**2 + 80**2)
    assert result is not None
    assert result.distance_cm == pytest.approx(expected, abs=0.01)
    assert result.distance_visual_cm == result.distance_cm
    if identifier == "1":
        assert result.distance_cm == projected.distance_cm
    runtime_pipeline._last_detection = result
    assert runtime_pipeline.detect(target=target).distance_cm == result.distance_cm


@pytest.mark.parametrize("disposition", [
    ObservationDisposition.ABSENT, ObservationDisposition.AMBIGUOUS,
    ObservationDisposition.REJECTED, ObservationDisposition.FAULT,
])
def test_non_detected_status_has_no_distance(disposition):
    detection = ArucoFrameDetection(disposition)
    assert detection.distance_cm is None
    assert "distance=" not in format_detection_status(detection)


@pytest.mark.parametrize("corners", [
    ((1, 1),) * 4,
    ((0, 0), (1, 1), (2, 2), (3, 3)),
    ((0, 0), (10, 10), (10, 0), (0, 10)),
    ((0, 0), (float("nan"), 0), (10, 10), (0, 10)),
    ((0, 0), (10, 0), (10, 10)),
])
def test_invalid_geometry_reports_unavailable(corners, runtime_pipeline, monkeypatch, caplog):
    marker_detector = runtime_pipeline._frame_processor._marker_detector
    _patch_marker_corners(monkeypatch, marker_detector, corners)
    frame = np.zeros((640, 480, 3), np.uint8)
    detection = marker_detector.detect(frame)
    assert detection.distance_cm is None
    if detection.disposition is ObservationDisposition.VALID:
        assert "distance=indisponible" in format_detection_status(detection)
    else:
        assert detection.disposition is ObservationDisposition.REJECTED
        assert "rejected" in format_detection_status(detection)
    assert runtime_pipeline._process_frame(frame, target="marker") is None
    assert "ArUco" in caplog.text


@pytest.mark.parametrize("success,translation", [
    (False, np.zeros((3, 1))),
    (True, np.array([[0], [0], [-80]])),
    (True, np.array([[0], [0], [float("nan")]])),
])
def test_failed_pose_does_not_produce_a_distance(
    monkeypatch, success, translation, runtime_pipeline, caplog,
):
    monkeypatch.setattr(cv2, "solvePnP", lambda *args, **kwargs: (success, None, translation))
    projected = _project_marker((0, 0, 80))
    marker_detector = runtime_pipeline._frame_processor._marker_detector
    _patch_marker_corners(monkeypatch, marker_detector, projected.corners_px)
    frame = np.zeros((640, 480, 3), np.uint8)
    detection = marker_detector.detect(frame)
    assert "distance=indisponible" in format_detection_status(detection)
    assert runtime_pipeline._process_frame(frame, target="marker") is None
    assert "Pose ArUco inexploitable" in caplog.text


def test_opencv_pose_error_is_logged_without_width_fallback(
    monkeypatch, runtime_pipeline, caplog,
):
    def fail(*args, **kwargs):
        raise cv2.error("synthetic pose failure")

    monkeypatch.setattr(cv2, "solvePnP", fail)
    projected = _project_marker((0, 0, 80))
    marker_detector = runtime_pipeline._frame_processor._marker_detector
    _patch_marker_corners(monkeypatch, marker_detector, projected.corners_px)
    frame = np.zeros((640, 480, 3), np.uint8)
    detection = marker_detector.detect(frame)
    assert "distance=indisponible" in format_detection_status(detection)
    assert runtime_pipeline._process_frame(frame, target="marker") is None
    assert "synthetic pose failure" in caplog.text


def test_overlay_shows_current_pose_distance_and_failures():
    texts = []
    drawing_api = SimpleNamespace(
        line=lambda *args: None, circle=lambda *args: None,
        putText=lambda frame, text, *args: texts.append(text),
        FONT_HERSHEY_SIMPLEX=0,
    )
    _draw_detection(object(), _project_marker((0, 0, 80)), drawing_api)
    _draw_detection(object(), _project_marker((20, 0, 80), yaw=30), drawing_api)
    invalid = ArucoFrameDetection(
        ObservationDisposition.VALID, TEST_MARKER_IDENTITY, ((1, 1),) * 4,
    )
    _draw_detection(object(), invalid, drawing_api)
    assert texts == [
        "ID 1 DETECTED ~80.0 cm", "ID 1 DETECTED ~82.5 cm",
        "ID 1 DETECTED - DISTANCE UNAVAILABLE",
    ]


@pytest.mark.parametrize("inference_error", [False, True])
def test_main_configures_reference_resolution_and_rotates_without_camera(monkeypatch, capsys, inference_error):
    from irobot.tools import vision_diagnostic

    calls = []
    texts = []
    boxes = []
    windows = []
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(frame, (180, 240), 25, (255, 0, 0), -1)
    cv2.circle(frame, (460, 240), 25, (255, 255, 0), -1)

    class Camera:
        camera_controls = {"ExposureValue": (-8.0, 8.0, 0.0)}

        @staticmethod
        def global_camera_info():
            return [{"Model": "ov5647"}]

        def __init__(self, index):
            assert index == 0

        def create_preview_configuration(self, *, main):
            assert main == {"size": (640, 480), "format": "BGR888"}
            return main

        def configure(self, config):
            calls.append("configure")

        def start(self):
            calls.append("start")

        def set_controls(self, controls):
            assert controls == {"ExposureValue": 1.0}
            calls.append("exposure")

        def capture_array(self):
            return frame

        def stop(self):
            calls.append("stop")

        def close(self):
            calls.append("camera_close")

    def detect(frame_rgb):
        assert frame_rgb.shape == (640, 480, 3)
        expected_rgb = FrameEnhancer(RuntimeSettings(camera_clahe_enabled=True)).apply(
            cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE),
        )
        np.testing.assert_array_equal(frame_rgb, expected_rgb)
        return _project_marker((0, 0, 80))

    monkeypatch.setenv("DISPLAY", ":test")
    monkeypatch.setitem(sys.modules, "picamera2", SimpleNamespace(Picamera2=Camera))

    def create_marker_detector(identity, *, focal_px, oriented_frame_size_px):
        assert focal_px == RuntimeSettings().camera_focal_px
        assert oriented_frame_size_px == RuntimeSettings().camera_oriented_frame_size_px
        return SimpleNamespace(detect=detect)

    monkeypatch.setattr(
        vision_diagnostic, "OpenCVMarkerDetector",
        create_marker_detector,
    )
    face = ObjectDetection(label="face", position="left", distance_cm=90, confidence=0.9)

    def detect_face(frame_rgb):
        expected_rgb = FrameEnhancer(RuntimeSettings(camera_clahe_enabled=True)).apply(
            cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE),
        )
        np.testing.assert_array_equal(frame_rgb, expected_rgb)
        if inference_error:
            raise cv2.error("synthetic diagnostic inference failure")
        return face

    monkeypatch.setattr(
        vision_diagnostic, "FaceDetector",
        lambda settings: SimpleNamespace(
            detect=detect_face, is_cached=True, bounding_box=(20, 150, 100, 110),
        ),
    )
    monkeypatch.setattr(cv2, "imshow", lambda name, image: windows.append((name, image.copy())))
    monkeypatch.setattr(cv2, "putText", lambda image, text, *args: texts.append(text))
    monkeypatch.setattr(cv2, "rectangle", lambda image, start, end, color, thickness: boxes.append(
        (start, end, color),
    ))
    monkeypatch.setattr(cv2, "waitKey", lambda *args: ord("q"))
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: calls.append("close"))
    if inference_error:
        with pytest.raises(cv2.error, match="diagnostic inference failure"):
            vision_diagnostic.main([])
        assert calls == ["configure", "exposure", "start", "stop", "camera_close", "close"]
        assert windows == []
        return
    assert vision_diagnostic.main([]) == 0
    assert calls == ["configure", "exposure", "start", "stop", "camera_close", "close"]
    output = capsys.readouterr().out
    assert "objectif non calibré" in output
    assert "distance=80.0 cm" in output
    assert "FACE: memorized; left; distance=90.0 cm" in output
    assert "BALL RED: detected" in output
    assert "BALL YELLOW: detected" in output
    assert len(texts) == 4
    assert len(boxes) == 3
    assert boxes[0][:2] == ((20, 150), (120, 260))
    assert windows[0][0] == "Vision - ArUco / Face / Red / Yellow"
    assert windows[0][1].shape == (640, 480, 3)
    assert "MEM" in texts[1]
    for text in texts[1:]:
        width = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)[0][0]
        assert width <= 480 - 12


def test_main_preview_only_skips_detection_and_shows_unannotated_frame(monkeypatch, capsys):
    from irobot.tools import vision_diagnostic

    calls = []
    windows = []
    frame = np.full((480, 640, 3), (10, 20, 30), dtype=np.uint8)

    class Camera:
        camera_controls = {"ExposureValue": (-8.0, 8.0, 0.0)}

        @staticmethod
        def global_camera_info():
            return [{"Model": "ov5647"}]

        def __init__(self, index):
            assert index == 0

        def create_preview_configuration(self, *, main):
            return main

        def configure(self, config):
            calls.append("configure")

        def start(self):
            calls.append("start")

        def set_controls(self, controls):
            calls.append("exposure")

        def capture_array(self):
            return frame

        def stop(self):
            calls.append("stop")

        def close(self):
            calls.append("camera_close")

    monkeypatch.setenv("DISPLAY", ":test")
    monkeypatch.setitem(sys.modules, "picamera2", SimpleNamespace(Picamera2=Camera))
    monkeypatch.setattr(vision_diagnostic, "OpenCVMarkerDetector", lambda *_: pytest.fail("ArUco detector started"))
    monkeypatch.setattr(vision_diagnostic, "FaceDetector", lambda *_: pytest.fail("face detector started"))
    monkeypatch.setattr(vision_diagnostic, "detect_balls", lambda *_: pytest.fail("ball detector started"))
    monkeypatch.setattr(cv2, "imshow", lambda name, image: windows.append((name, image.copy())))
    monkeypatch.setattr(cv2, "putText", lambda *args: pytest.fail("frame annotated"))
    monkeypatch.setattr(cv2, "rectangle", lambda *args: pytest.fail("frame annotated"))
    monkeypatch.setattr(cv2, "waitKey", lambda *args: ord("q"))
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: calls.append("close"))

    assert vision_diagnostic.main(["--preview-only"]) == 0

    assert calls == ["configure", "exposure", "start", "stop", "camera_close", "close"]
    assert windows[0][0] == "Vision - Preview"
    expected_rgb = FrameEnhancer(RuntimeSettings()).apply(cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE))
    np.testing.assert_array_equal(windows[0][1], cv2.cvtColor(expected_rgb, cv2.COLOR_RGB2BGR))
    assert "Aperçu caméra uniquement" in capsys.readouterr().out


def test_both_balls_are_detected_independently_with_existing_distance_model():
    frame = np.zeros((640, 480, 3), np.uint8)
    cv2.circle(frame, (100, 320), 25, (255, 0, 0), -1)
    cv2.circle(frame, (380, 320), 35, (255, 255, 0), -1)
    results = detect_balls(frame, RuntimeSettings(camera_ball_diameter_cm=6, camera_focal_px=680))
    red, red_box = results["red"]
    yellow, yellow_box = results["yellow"]
    assert red.label == "red_ball" and red.position == "left"
    assert yellow.label == "yellow_ball" and yellow.position == "right"
    assert red.distance_cm == pytest.approx(680 * 6 / red.diameter_px)
    assert yellow.distance_cm == pytest.approx(680 * 6 / yellow.diameter_px)
    assert red_box[2] == 49
    assert yellow_box[2] == 69
    assert red.distance_cm > yellow.distance_cm


def test_ball_without_bounding_box_is_reported_as_detector_contract_error(monkeypatch):
    from irobot.tools import vision_diagnostic

    monkeypatch.setattr(
        vision_diagnostic.ColorDetector,
        "detect",
        lambda detector, frame: ObjectDetection(label=f"{detector.color_name}_ball"),
    )
    with pytest.raises(RuntimeError, match="missing its bounding box"):
        detect_balls(np.zeros((640, 480, 3), np.uint8), RuntimeSettings())


def test_absent_balls_and_nonball_objects_are_not_reported_as_balls(monkeypatch):
    from irobot.tools import vision_diagnostic

    frame = np.zeros((640, 480, 3), np.uint8)
    monkeypatch.setattr(
        vision_diagnostic.ColorDetector,
        "detect",
        lambda detector, frame: ObjectDetection(
            label=f"{detector.color_name}_object", bbox_px=(100, 200, 50, 50),
        ),
    )
    assert detect_balls(frame, RuntimeSettings()) == {"red": None, "yellow": None}


def test_object_status_distinguishes_absence_detection_and_cached_face():
    assert format_object_status("FACE", None, cached=True) == "FACE: absent"
    detection = ObjectDetection(label="face", position="center", distance_cm=100, confidence=0.8)
    assert format_object_status("FACE", detection) == (
        "FACE: detected; center; distance=100.0 cm; confidence=0.80"
    )
    assert "memorized" in format_object_status("FACE", detection, cached=True)
    detection.distance_cm = None
    assert "distance=indisponible" in format_object_status("FACE", detection)
