from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path
import tempfile
from unittest.mock import patch

from irobot.config import settings
from irobot.interfaces.human_perception import (
    ArucoFrameDetection,
    AcquisitionReason,
    AcquisitionStatus,
    HumanMarkerMissionContext,
    HumanMarkerAcquisition,
    MarkerIdentity,
    MarkerObservation,
    MarkerQuality,
    OpenCVArucoMarkerDecoder,
    ObservationDisposition,
)


class FakeArucoDetector:
    def __init__(self):
        self.result = ([], None, [])

    def detectMarkers(self, _image):
        return self.result


class FakeArucoApi:
    DICT_4X4_50 = 7

    def __init__(self):
        self.detector = FakeArucoDetector()

    @staticmethod
    def getPredefinedDictionary(code):
        return ("dictionary", code)

    @staticmethod
    def DetectorParameters():
        return "parameters"

    def ArucoDetector(self, dictionary, parameters):
        if dictionary != ("dictionary", self.DICT_4X4_50) or parameters != "parameters":
            raise AssertionError("Unexpected ArUco API configuration")
        return self.detector


class HumanMarkerAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.identity = MarkerIdentity("unselected-family", "unselected-dictionary", "configured-id")
        self.acquisition = HumanMarkerAcquisition(
            expected_identity=self.identity,
            mission_id="mission-1",
            context_version="context-1",
            max_age_seconds=HumanMarkerAcquisition.MAX_AGE_TARGET_SECONDS,
        )

    def observation(self, frame_number: int, **changes) -> MarkerObservation:
        observation = MarkerObservation(
            source_id="camera-1",
            stream_generation="stream-1",
            frame_number=frame_number,
            captured_at=float(frame_number) * 0.01,
            published_at=float(frame_number) * 0.01 + 0.005,
            mission_id="mission-1",
            context_version="context-1",
            disposition=ObservationDisposition.VALID,
            identity=self.identity,
            image_width_px=640,
            image_height_px=480,
            center_x_px=320.0,
            center_y_px=240.0,
            bearing_deg=0.0,
            optical_distance_cm=160.0,
            robot_clearance_cm=150.0,
            calibration_version="calibration-1",
            quality=MarkerQuality(True, True, 0.1, 0.2, 5.0),
        )
        return replace(observation, **changes)

    def test_acquires_only_after_three_distinct_consecutive_fresh_frames(self):
        first = self.acquisition.observe(self.observation(1), now=0.02)
        second = self.acquisition.observe(self.observation(2), now=0.03)
        third = self.acquisition.observe(self.observation(3), now=0.04)

        self.assertEqual((first.status, first.confirmations),
                         (AcquisitionStatus.CONFIRMING, 1))
        self.assertEqual((second.status, second.confirmations),
                         (AcquisitionStatus.CONFIRMING, 2))
        self.assertEqual((third.status, third.reason),
                         (AcquisitionStatus.ACQUIRED, AcquisitionReason.ACQUIRED))

    def test_age_is_measured_from_capture_not_publication_and_boundary_is_inclusive(self):
        observation = self.observation(1, captured_at=1.0, published_at=1.19)
        result = self.acquisition.observe(observation, now=1.2)
        self.assertEqual(result.status, AcquisitionStatus.CONFIRMING)

        self.acquisition.reset()
        stale = replace(observation, published_at=1.2)
        result = self.acquisition.observe(stale, now=1.200001)
        self.assertEqual(result.reason, AcquisitionReason.STALE)

    def test_duplicate_frame_does_not_confirm_or_refresh_observation(self):
        self.acquisition.observe(self.observation(1), now=0.02)
        duplicate = self.acquisition.observe(self.observation(1), now=0.03)
        self.assertEqual(duplicate.reason, AcquisitionReason.DUPLICATE_FRAME)
        self.assertEqual(duplicate.confirmations, 0)

    def test_all_confirmation_captures_must_still_be_fresh_at_acquisition(self):
        for final_capture, expected in (
            (0.2, AcquisitionStatus.ACQUIRED),
            (0.200001, AcquisitionStatus.CONFIRMING),
        ):
            with self.subTest(final_capture=final_capture):
                self.acquisition.reset()
                for number, captured in enumerate((0.0, 0.1, final_capture), start=1):
                    result = self.acquisition.observe(
                        self.observation(number, captured_at=captured, published_at=captured),
                        now=captured,
                    )
                self.assertEqual(result.status, expected)
                self.assertEqual(result.confirmations, 3 if expected is AcquisitionStatus.ACQUIRED else 2)
                if expected is AcquisitionStatus.CONFIRMING:
                    result = self.acquisition.observe(
                        self.observation(4, captured_at=0.21, published_at=0.21), now=0.21,
                    )
                    self.assertEqual(result.status, AcquisitionStatus.ACQUIRED)

    def test_acquired_continuity_uses_new_valid_frames_without_reacquiring_each_time(self):
        for number in range(1, 4):
            self.acquisition.observe(self.observation(number), now=number * 0.01 + 0.005)
        for number, captured in ((4, 0.15), (5, 0.3), (6, 0.45)):
            result = self.acquisition.observe(
                self.observation(number, captured_at=captured, published_at=captured), now=captured,
            )
            self.assertEqual((result.status, result.confirmations), (AcquisitionStatus.ACQUIRED, 3))
        rejected = self.acquisition.observe(
            self.observation(7, captured_at=0.5, published_at=0.5,
                             disposition=ObservationDisposition.ABSENT), now=0.5,
        )
        self.assertEqual(rejected.status, AcquisitionStatus.REJECTED)
        fresh = self.acquisition.observe(
            self.observation(8, captured_at=0.6, published_at=0.6), now=0.6,
        )
        self.assertEqual((fresh.status, fresh.confirmations), (AcquisitionStatus.CONFIRMING, 1))

    def test_frame_gap_restarts_confirmations(self):
        self.acquisition.observe(self.observation(1), now=0.02)
        gap = self.acquisition.observe(self.observation(3), now=0.04)
        self.assertEqual(gap.reason, AcquisitionReason.FRAME_GAP)
        next_frame = self.acquisition.observe(self.observation(4), now=0.05)
        self.assertEqual((next_frame.status, next_frame.confirmations),
                         (AcquisitionStatus.CONFIRMING, 1))

    def test_stream_restart_invalidates_prior_confirmations(self):
        self.acquisition.observe(self.observation(1), now=0.02)
        changed = self.acquisition.observe(
            self.observation(2, stream_generation="stream-2"), now=0.03,
        )
        self.assertEqual(changed.reason, AcquisitionReason.STREAM_CHANGED)
        next_frame = self.acquisition.observe(
            self.observation(3, stream_generation="stream-2"), now=0.04,
        )
        self.assertEqual(next_frame.confirmations, 1)

    def test_mission_context_and_identity_mismatches_are_rejected(self):
        cases = (
            ({"mission_id": "mission-2"}, AcquisitionReason.MISSION_MISMATCH),
            ({"context_version": "context-2"}, AcquisitionReason.CONTEXT_MISMATCH),
            ({"identity": MarkerIdentity("other", "other", "other")},
             AcquisitionReason.IDENTITY_MISMATCH),
        )
        for changes, reason in cases:
            with self.subTest(reason=reason):
                self.acquisition.reset()
                result = self.acquisition.observe(self.observation(1, **changes), now=0.02)
                self.assertEqual(result.reason, reason)

    def test_mission_context_snapshots_persistent_identity_for_acquisition(self):
        context = HumanMarkerMissionContext.from_runtime_settings(
            settings.RuntimeSettings(human_marker_identity=self.identity),
            mission_id="mission-locked",
            context_version="context-locked",
        )
        acquisition = context.new_acquisition(max_age_seconds=0.2)

        self.assertEqual(acquisition.expected_identity, self.identity)
        self.assertEqual(acquisition.mission_id, "mission-locked")
        self.assertEqual(acquisition.context_version, "context-locked")
        with self.assertRaises(ValueError):
            HumanMarkerMissionContext.from_runtime_settings(
                settings.RuntimeSettings(),
                mission_id="mission-unconfigured",
                context_version="context-unconfigured",
            )

    def test_invalid_or_ambiguous_observation_clears_confirmation(self):
        self.acquisition.observe(self.observation(1), now=0.02)
        invalid = self.acquisition.observe(
            self.observation(
                2, disposition=ObservationDisposition.AMBIGUOUS,
                reason="multiple_configured_markers",
            ),
            now=0.03,
        )
        self.assertEqual(invalid.reason, AcquisitionReason.OBSERVATION_AMBIGUOUS)
        self.assertEqual(invalid.detail, "multiple_configured_markers")
        next_frame = self.acquisition.observe(self.observation(3), now=0.04)
        self.assertEqual(next_frame.confirmations, 1)

    def test_explicit_stale_disposition_is_not_treated_as_absence(self):
        result = self.acquisition.observe(
            self.observation(
                1, disposition=ObservationDisposition.STALE, reason="frame_expired",
            ),
            now=0.02,
        )
        self.assertEqual(result.reason, AcquisitionReason.STALE)
        self.assertEqual(result.detail, "frame_expired")

    def test_missing_or_invalid_geometry_never_acquires(self):
        cases = (
            ({"quality": None}, AcquisitionReason.GEOMETRY_INVALID),
            ({"quality": "malformed"}, AcquisitionReason.GEOMETRY_INVALID),
            ({"quality": MarkerQuality(False, True)}, AcquisitionReason.GEOMETRY_INVALID),
            ({"optical_distance_cm": None}, AcquisitionReason.GEOMETRY_INVALID),
            ({"robot_clearance_cm": 0.0}, AcquisitionReason.GEOMETRY_INVALID),
        )
        for changes, reason in cases:
            with self.subTest(changes=changes):
                self.acquisition.reset()
                result = self.acquisition.observe(self.observation(1, **changes), now=0.02)
                self.assertEqual(result.reason, reason)

    def test_future_and_incoherent_timestamps_are_rejected(self):
        future = self.acquisition.observe(self.observation(1, captured_at=0.03), now=0.02)
        self.assertEqual(future.reason, AcquisitionReason.TIMESTAMP_INCOHERENT)
        incoherent = self.acquisition.observe(
            self.observation(1, published_at=0.005), now=0.02,
        )
        self.assertEqual(incoherent.reason, AcquisitionReason.TIMESTAMP_INCOHERENT)

    def test_capture_and_publication_times_must_not_regress_within_a_stream(self):
        first = self.acquisition.observe(self.observation(1), now=0.02)
        regressed = self.acquisition.observe(
            self.observation(2, captured_at=0.005, published_at=0.02), now=0.03,
        )
        self.assertEqual(first.status, AcquisitionStatus.CONFIRMING)
        self.assertEqual(regressed.reason, AcquisitionReason.TIMESTAMP_INCOHERENT)

    def test_invalid_freshness_budget_is_rejected(self):
        with self.assertRaises(ValueError):
            HumanMarkerAcquisition(
                expected_identity=self.identity,
                mission_id="mission-1",
                context_version="context-1",
                max_age_seconds=float("nan"),
            )

    def test_opencv_aruco_decoder_returns_only_the_configured_marker_corners(self):
        identity = MarkerIdentity("aruco", "DICT_4X4_50", "5")
        api = FakeArucoApi()
        api.detector.result = (
            [[[[10, 10], [30, 10], [30, 30], [10, 30]]]],
            [[5]],
            [],
        )

        decoded = OpenCVArucoMarkerDecoder(identity, aruco_api=api).detect(object())

        self.assertEqual(decoded, ArucoFrameDetection(
            ObservationDisposition.VALID,
            identity,
            ((10.0, 10.0), (30.0, 10.0), (30.0, 30.0), (10.0, 30.0)),
        ))

    def test_selected_static_test_marker_identity_is_recognized_without_fallback(self):
        identity = MarkerIdentity("aruco", "DICT_4X4_50", "1")
        api = FakeArucoApi()
        api.detector.result = (
            [[[[10, 10], [30, 10], [30, 30], [10, 30]]]],
            [[1]],
            [],
        )

        decoded = OpenCVArucoMarkerDecoder(identity, aruco_api=api).detect(object())

        self.assertEqual(decoded.disposition, ObservationDisposition.VALID)
        self.assertEqual(decoded.identity, identity)
        self.assertEqual(decoded.corners_px, (
            (10.0, 10.0), (30.0, 10.0), (30.0, 30.0), (10.0, 30.0),
        ))

    def test_opencv_aruco_decoder_does_not_substitute_another_id(self):
        identity = MarkerIdentity("aruco", "DICT_4X4_50", "5")
        api = FakeArucoApi()
        api.detector.result = (
            [[[[10, 10], [30, 10], [30, 30], [10, 30]]]],
            [[6]],
            [],
        )
        decoded = OpenCVArucoMarkerDecoder(identity, aruco_api=api).detect(object())
        self.assertEqual(decoded.disposition, ObservationDisposition.ABSENT)

    def test_opencv_aruco_decoder_rejects_duplicate_expected_ids(self):
        identity = MarkerIdentity("aruco", "DICT_4X4_50", "5")
        api = FakeArucoApi()
        corners = [[[[1, 1], [2, 1], [2, 2], [1, 2]]]]
        api.detector.result = ([*corners, *corners], [[5], [5]], [])
        decoded = OpenCVArucoMarkerDecoder(identity, aruco_api=api).detect(object())
        self.assertEqual(decoded.disposition, ObservationDisposition.AMBIGUOUS)
        self.assertEqual(decoded.reason, "multiple_configured_markers")

    def test_opencv_aruco_decoder_reports_malformed_results(self):
        identity = MarkerIdentity("aruco", "DICT_4X4_50", "5")
        api = FakeArucoApi()
        api.detector.result = ([[[[1, 1], [2, 1]]]], [[5]], [])
        malformed = OpenCVArucoMarkerDecoder(identity, aruco_api=api).detect(object())
        self.assertEqual(malformed.disposition, ObservationDisposition.REJECTED)

        api.detector.result = ([], [[5]], [])
        mismatch = OpenCVArucoMarkerDecoder(identity, aruco_api=api).detect(object())
        self.assertEqual(mismatch.disposition, ObservationDisposition.FAULT)

    def test_opencv_aruco_decoder_requires_explicit_supported_configuration(self):
        with self.assertRaises(ValueError):
            OpenCVArucoMarkerDecoder(
                MarkerIdentity("aruco", "DICT_UNKNOWN", "5"),
                aruco_api=FakeArucoApi(),
            )
        with self.assertRaises(ValueError):
            OpenCVArucoMarkerDecoder(
                MarkerIdentity("aruco", "DICT_4X4_50", "05"),
                aruco_api=FakeArucoApi(),
            )

    def test_marker_identity_persists_in_runtime_toml_and_missing_is_not_replaced(self):
        configured = (
            '[human_marker]\n'
            'family = "aruco"\n'
            'dictionary = "DICT_4X4_50"\n'
            'identifier = "42"\n'
        )
        with tempfile.TemporaryDirectory(prefix="human-marker-config-") as directory:
            config_path = Path(directory) / "runtime_calibration.toml"
            config_path.write_text(configured, encoding="utf-8")
            with patch("irobot.config.settings._config_file", return_value=config_path):
                loaded = settings.load_runtime_settings()
            self.assertEqual(
                loaded.human_marker_identity,
                MarkerIdentity("aruco", "DICT_4X4_50", "42"),
            )

        with tempfile.TemporaryDirectory(prefix="human-marker-config-") as directory:
            config_path = Path(directory) / "runtime_calibration.toml"
            config_path.write_text("[runtime]\ncm_per_second = 25.0\n", encoding="utf-8")
            with patch("irobot.config.settings._config_file", return_value=config_path):
                loaded = settings.load_runtime_settings()
            self.assertIsNone(loaded.human_marker_identity)

    def test_partial_or_malformed_persistent_marker_identity_is_an_error(self):
        cases = (
            '[human_marker]\nfamily = "aruco"\nidentifier = "42"\n',
            '[human_marker]\nfamily = "aruco"\ndictionary = "DICT_4X4_50"\nidentifier = 42\n',
        )
        for contents in cases:
            with self.subTest(contents=contents):
                with tempfile.TemporaryDirectory(prefix="human-marker-config-") as directory:
                    config_path = Path(directory) / "runtime_calibration.toml"
                    config_path.write_text(contents, encoding="utf-8")
                    with patch("irobot.config.settings._config_file", return_value=config_path):
                        with self.assertRaises(ValueError):
                            settings.load_runtime_settings()


if __name__ == "__main__":
    unittest.main()
