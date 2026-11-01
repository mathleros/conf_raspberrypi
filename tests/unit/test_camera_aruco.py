import cv2
import numpy as np
import pytest

from irobot.config.settings import MarkerIdentity, RuntimeSettings
from irobot.hardware.camera import camera_live_pipeline
from irobot.interfaces.human_perception_contracts import (
    ArucoFrameDetection, ObservationDisposition,
)


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
    assert detection.distance_cm == pytest.approx(8 * 600 / 79)
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
    assert detection.distance_cm == 60


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
    assert "Largeur apparente ArUco invalide" in caplog.text


def test_marker_distance_is_not_fused_with_ultrasound(pipeline):
    pipeline.fusion_enabled = True

    def unexpected_read():
        pytest.fail("Marker distance must remain the pinhole estimate")

    pipeline.distance_reader = unexpected_read
    pipeline._last_detection = pipeline._process_frame(_frame())
    assert pipeline.detect(target="marker").distance_cm == pytest.approx(8 * 600 / 79)
