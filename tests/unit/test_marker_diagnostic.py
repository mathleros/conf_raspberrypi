import math
import sys
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from irobot.interfaces.aruco_marker_decoder import ArucoFrameDetection, ObservationDisposition
from irobot.interfaces.marker_diagnostic import (
    TEST_MARKER_IDENTITY,
    _draw_detection,
    compute_marker_distance_cm,
    format_detection_status,
)


def _project_marker(translation, yaw=0, pitch=0, roll=0, size=(480, 640)):
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
    image_points *= (600 * width / 480, 600 * height / 640)
    image_points += (width / 2, height / 2)
    return ArucoFrameDetection(
        ObservationDisposition.VALID, TEST_MARKER_IDENTITY,
        tuple((float(x), float(y)) for x, y in image_points),
    )


@pytest.mark.parametrize("x", [-20, 0, 20])
@pytest.mark.parametrize("yaw", [-45, 0, 45])
@pytest.mark.parametrize("pitch,roll", [(0, 0), (25, 30)])
def test_distance_accounts_for_position_and_orientation(x, yaw, pitch, roll):
    translation = (x, 0, 80)
    detection = _project_marker(translation, yaw, pitch, roll)
    assert compute_marker_distance_cm(detection) == pytest.approx(
        math.dist((0, 0, 0), translation), abs=0.01,
    )


def test_centered_frontal_distance_preserves_previous_result():
    detection = _project_marker((0, 0, 100))
    assert compute_marker_distance_cm(detection) == pytest.approx(100, abs=0.01)
    assert "distance=100.0 cm" in format_detection_status(detection)


def test_tilted_off_axis_distance_is_not_based_on_width_only():
    detection = _project_marker((20, 0, 80), yaw=-30)
    corners = detection.corners_px
    width = (math.dist(corners[0], corners[1]) + math.dist(corners[3], corners[2])) / 2
    expected = math.hypot(20, 80)
    assert abs(4800 / width - expected) > 5
    assert compute_marker_distance_cm(detection) == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize("x", [-20, 20])
def test_84_cm_off_axis_with_subpixel_corner_noise(x):
    detection = _project_marker((x, 0, math.sqrt(84**2 - x**2)), yaw=-30)
    noise = ((0.1, -0.2), (-0.1, 0.2), (0.2, 0.1), (-0.2, -0.1))
    noisy_corners = tuple(
        (x + dx, y + dy) for (x, y), (dx, dy) in zip(detection.corners_px, noise)
    )
    noisy_detection = ArucoFrameDetection(
        ObservationDisposition.VALID, TEST_MARKER_IDENTITY, noisy_corners,
    )
    assert compute_marker_distance_cm(noisy_detection) == pytest.approx(84, abs=1)


@pytest.mark.parametrize("size", [(480, 640), (960, 1280)])
def test_distance_uses_actual_frame_dimensions(size):
    detection = _project_marker((20, 10, 80), yaw=30, size=size)
    assert compute_marker_distance_cm(detection, size) == pytest.approx(
        math.sqrt(20**2 + 10**2 + 80**2), abs=0.01,
    )


@pytest.mark.parametrize("disposition", [
    ObservationDisposition.ABSENT, ObservationDisposition.AMBIGUOUS,
    ObservationDisposition.REJECTED, ObservationDisposition.FAULT,
])
def test_non_detected_status_has_no_distance(disposition):
    detection = ArucoFrameDetection(disposition)
    assert compute_marker_distance_cm(detection) is None
    assert "distance=" not in format_detection_status(detection)


@pytest.mark.parametrize("corners", [
    ((1, 1),) * 4,
    ((0, 0), (1, 1), (2, 2), (3, 3)),
    ((0, 0), (10, 10), (10, 0), (0, 10)),
    ((0, 0), (float("nan"), 0), (10, 10), (0, 10)),
    ((0, 0), (10, 0), (10, 10)),
])
def test_invalid_geometry_reports_unavailable(corners):
    detection = ArucoFrameDetection(
        ObservationDisposition.VALID, TEST_MARKER_IDENTITY, corners,
    )
    assert compute_marker_distance_cm(detection) is None
    assert "distance=indisponible" in format_detection_status(detection)


@pytest.mark.parametrize("success,translation", [
    (False, np.zeros((3, 1))),
    (True, np.array([[0], [0], [-80]])),
    (True, np.array([[0], [0], [float("nan")]])),
])
def test_failed_pose_does_not_produce_a_distance(monkeypatch, success, translation):
    monkeypatch.setattr(cv2, "solvePnP", lambda *args, **kwargs: (success, None, translation))
    assert "distance=indisponible" in format_detection_status(_project_marker((0, 0, 80)))


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


def test_main_configures_reference_resolution_and_rotates_without_camera(monkeypatch, capsys):
    from irobot.interfaces import marker_diagnostic

    calls = []
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    class Camera:
        @staticmethod
        def global_camera_info():
            return [{"Model": "ov5647"}]

        def __init__(self, index):
            assert index == 0

        def create_preview_configuration(self, *, main):
            assert main == {"size": (640, 480)}
            return main

        def configure(self, config):
            calls.append("configure")

        def start(self):
            calls.append("start")

        def capture_array(self):
            return frame

        def stop(self):
            calls.append("stop")

    def detect(grayscale):
        assert grayscale.shape == (640, 480)
        return _project_marker((0, 0, 80))

    monkeypatch.setenv("DISPLAY", ":test")
    monkeypatch.setitem(sys.modules, "picamera2", SimpleNamespace(Picamera2=Camera))
    monkeypatch.setattr(
        marker_diagnostic, "OpenCVArucoMarkerDecoder",
        lambda identity: SimpleNamespace(detect=detect),
    )
    monkeypatch.setattr(cv2, "imshow", lambda *args: None)
    monkeypatch.setattr(cv2, "waitKey", lambda *args: ord("q"))
    monkeypatch.setattr(cv2, "destroyAllWindows", lambda: calls.append("close"))
    assert marker_diagnostic.main() == 0
    assert calls == ["configure", "start", "stop", "close"]
    output = capsys.readouterr().out
    assert "objectif non calibré" in output
    assert "distance=80.0 cm" in output
