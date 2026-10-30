from __future__ import annotations

import unittest

from irobot.config.settings import MarkerIdentity
from irobot.interfaces.human_perception import (
    ArucoFrameDetection,
    ObservationDisposition,
)
from irobot.interfaces.marker_diagnostic import (
    TEST_MARKER_IDENTITY,
    format_detection_status,
)


class MarkerDiagnosticTests(unittest.TestCase):
    def test_selected_identity_is_explicit_and_not_a_production_configuration(self):
        self.assertEqual(
            TEST_MARKER_IDENTITY,
            MarkerIdentity("aruco", "DICT_4X4_50", "1"),
        )

    def test_detected_status_reports_only_marker_corners_in_pixels(self):
        detection = ArucoFrameDetection(
            ObservationDisposition.VALID,
            TEST_MARKER_IDENTITY,
            ((10.0, 11.0), (20.0, 11.0), (20.0, 21.0), (10.0, 21.0)),
        )

        message = format_detection_status(detection)

        self.assertIn("ID 1: detected", message)
        self.assertIn("corners_px=", message)
        self.assertNotIn("cm", message)
        self.assertNotIn("distance", message)

    def test_absence_ambiguity_and_fault_remain_distinct(self):
        self.assertEqual(
            format_detection_status(ArucoFrameDetection(ObservationDisposition.ABSENT)),
            "ID 1: absent",
        )
        self.assertEqual(
            format_detection_status(ArucoFrameDetection(
                ObservationDisposition.AMBIGUOUS,
                TEST_MARKER_IDENTITY,
                reason="multiple_configured_markers",
            )),
            "ID 1: ambiguous; reason=multiple_configured_markers",
        )
        self.assertEqual(
            format_detection_status(ArucoFrameDetection(
                ObservationDisposition.FAULT,
                reason="camera_or_decoder_fault",
            )),
            "ID 1: fault; reason=camera_or_decoder_fault",
        )

    def test_valid_status_without_corners_is_not_reported_as_detected(self):
        self.assertEqual(
            format_detection_status(ArucoFrameDetection(ObservationDisposition.VALID)),
            "ID 1: invalid detector result (identity or corners unavailable)",
        )

    def test_valid_status_with_a_different_identity_is_not_reported_as_selected(self):
        detection = ArucoFrameDetection(
            ObservationDisposition.VALID,
            MarkerIdentity("aruco", "DICT_4X4_50", "2"),
            ((10.0, 11.0), (20.0, 11.0), (20.0, 21.0), (10.0, 21.0)),
        )
        self.assertEqual(
            format_detection_status(detection),
            "ID 1: invalid detector result (identity or corners unavailable)",
        )


if __name__ == "__main__":
    unittest.main()
