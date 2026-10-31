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
    HumanPerceptionFrame,
    HumanPerceptionProvider,
    MarkerIdentity,
    MarkerObservation,
    MarkerQuality,
    OpenCVArucoMarkerDecoder,
    ObservationDisposition,
    validate_marker_observation,
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


class SyntheticHumanPerceptionProvider:
    """Only fictional pixels, geometry, calibration and simulated timestamps."""

    def __init__(self, **changes: object) -> None:
        self.changes = changes

    def observe(
        self, frame: HumanPerceptionFrame, *, context: HumanMarkerMissionContext,
    ) -> MarkerObservation:
        return replace(MarkerObservation(
            source_id=frame.source_id,
            stream_generation=frame.stream_generation,
            frame_number=frame.frame_number,
            captured_at=frame.captured_at,
            published_at=frame.published_at,
            mission_id=context.mission_id,
            context_version=context.context_version,
            disposition=ObservationDisposition.VALID,
            identity=context.identity,
            image_width_px=100,
            image_height_px=100,
            center_x_px=50.0,
            center_y_px=50.0,
            bearing_deg=0.0,
            optical_distance_cm=12.0,
            robot_clearance_cm=10.0,
            calibration_version="fictional-calibration",
            quality=MarkerQuality(True, True),
        ), **self.changes)


class HumanPerceptionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.context = HumanMarkerMissionContext(
            "synthetic-mission", "synthetic-context",
            MarkerIdentity("fictional-family", "fictional-dictionary", "fictional-id"),
        )
        self.provider: HumanPerceptionProvider = SyntheticHumanPerceptionProvider()
        self.acquisition = self.context.new_acquisition(max_age_seconds=0.2)

    @staticmethod
    def frame(number: int = 1, captured: float = 0.0, **changes) -> HumanPerceptionFrame:
        return replace(HumanPerceptionFrame(
            "synthetic-source", "synthetic-stream", number, captured, captured, object(),
        ), **changes)

    def result(self, frame: HumanPerceptionFrame, **changes) -> MarkerObservation:
        provider: HumanPerceptionProvider = SyntheticHumanPerceptionProvider(**changes)
        return provider.observe(frame, context=self.context)

    def assess(self, number: int, captured: float, **changes):
        frame = self.frame(number, captured)
        return self.acquisition.observe_frame(
            frame, self.result(frame, **changes), now=captured,
        )

    def test_nominal_result_is_returned_unchanged_without_inspecting_opaque_pixels(self):
        frame = self.frame(captured=1.0, published_at=1.1)
        pixels = frame.image
        observation = self.provider.observe(frame, context=self.context)
        validated = validate_marker_observation(
            frame, observation, context=self.context, now=1.1,
        )
        self.assertIs(validated, observation)
        self.assertEqual((validated.captured_at, validated.published_at), (1.0, 1.1))
        self.assertIs(frame.image, pixels)

    def test_result_must_match_each_frame_and_context_coordinate(self):
        frame = self.frame(7, 1.0, published_at=1.1)
        changes = (
            ("source_id", "another-source"),
            ("stream_generation", "old-stream"),
            ("frame_number", 6),
            ("captured_at", 1.05),
            ("mission_id", "another-mission"),
            ("context_version", "obsolete-context"),
            ("identity", MarkerIdentity("other", "other", "other")),
        )
        for name, value in changes:
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, name):
                    validate_marker_observation(
                        frame, self.result(frame, **{name: value}),
                        context=self.context, now=1.2,
                    )

    def test_frame_and_result_publications_are_distinct_with_inclusive_ordering(self):
        frame = self.frame(captured=1.0, published_at=1.1)
        for published in (1.1, 1.2):
            with self.subTest(published=published):
                observation = self.result(frame, published_at=published)
                self.assertIs(validate_marker_observation(
                    frame, observation, context=self.context, now=1.2,
                ), observation)
                self.assertEqual(observation.captured_at, 1.0)
        for published in (0.9, 1.05, 1.200001):
            with self.subTest(published=published):
                with self.assertRaisesRegex(ValueError, "publication|timestamps"):
                    validate_marker_observation(
                        frame, self.result(frame, published_at=published),
                        context=self.context, now=1.2,
                    )

    def test_invalid_frame_or_result_coordinates_and_timestamps_are_explicit_errors(self):
        frame = self.frame(captured=1.0)
        malformed = (
            ("source_id", ""), ("source_id", None), ("source_id", True),
            ("stream_generation", ""), ("stream_generation", 1),
            ("frame_number", True), ("frame_number", -1), ("frame_number", 1.0),
            ("frame_number", "1"),
        )
        bad_times = (None, True, "1", float("nan"), float("inf"), -float("inf"), 10**1000)
        malformed += tuple(
            (name, value) for name in ("captured_at", "published_at") for value in bad_times
        )
        for name, value in malformed:
            for target in ("frame", "result"):
                with self.subTest(name=name, value=value, target=target):
                    candidate = replace(frame, **{name: value}) if target == "frame" else frame
                    observation = self.result(frame, **{name: value}) if target == "result" else self.result(frame)
                    with self.assertRaises(ValueError):
                        validate_marker_observation(
                            candidate, observation, context=self.context, now=1.0,
                        )
        for now in (*bad_times, 0.999999):
            with self.subTest(now=now):
                with self.assertRaisesRegex(ValueError, "timestamps"):
                    validate_marker_observation(
                        frame, self.result(frame), context=self.context, now=now,
                    )
        for changes in (
            {"captured_at": 1.1}, {"published_at": 0.9}, {"published_at": 1.1},
        ):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, "timestamps"):
                    validate_marker_observation(
                        replace(frame, **changes), self.result(frame),
                        context=self.context, now=1.0,
                    )

    def test_wrong_outer_types_and_malformed_producer_returns_have_no_fallback(self):
        frame = self.frame()
        observation = self.result(frame)
        for malformed in (None, {}, (), "valid", object()):
            with self.subTest(malformed=malformed):
                with self.assertRaises(TypeError):
                    validate_marker_observation(
                        malformed, observation, context=self.context, now=0.0,
                    )
                with self.assertRaises(TypeError):
                    validate_marker_observation(
                        frame, observation, context=malformed, now=0.0,
                    )
                with patch.object(self.provider, "observe", return_value=malformed):
                    returned = self.provider.observe(frame, context=self.context)
                self.acquisition.reset()
                for n in range(1, 4):
                    self.assess(n, n * 0.01)
                next_frame = self.frame(4, 0.04)
                with self.assertRaisesRegex(TypeError, "MarkerObservation"):
                    self.acquisition.observe_frame(next_frame, returned, now=0.04)
                fresh = self.acquisition.observe_frame(
                    next_frame, self.result(next_frame), now=0.04,
                )
                self.assertEqual(
                    (fresh.status, fresh.confirmations), (AcquisitionStatus.CONFIRMING, 1),
                )

    def test_malformed_optional_result_fields_and_dispositions_are_not_repaired(self):
        frame = self.frame()
        changes = (
            {"mission_id": None}, {"context_version": True},
            {"disposition": "valid"}, {"disposition": []}, {"disposition": {}},
            {"disposition": None}, {"identity": "fictional-id"},
            {"quality": {}}, {"quality": MarkerQuality(1, True)},
            {"quality": MarkerQuality(True, 1)},
            {"reason": {}}, {"calibration_version": 1},
        )
        changes += tuple(
            {name: value}
            for name in ("image_width_px", "image_height_px")
            for value in (True, "100", 100.0)
        )
        changes += tuple(
            {name: value}
            for name in ("center_x_px", "center_y_px", "bearing_deg",
                         "optical_distance_cm", "robot_clearance_cm")
            for value in (True, "10", float("nan"), float("inf"), 10**1000)
        )
        changes += tuple(
            {"quality": replace(MarkerQuality(True, True), **{name: value})}
            for name in ("blur_metric", "reprojection_error_px", "obliqueness_deg")
            for value in (True, "0", float("nan"), float("inf"))
        )
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    validate_marker_observation(
                        frame, self.result(frame, **change), context=self.context, now=0.0,
                    )

    def test_no_geometry_or_identity_is_invented_to_make_a_result_acquirable(self):
        for changes, expected in (
            ({"quality": None}, AcquisitionReason.GEOMETRY_INVALID),
            ({"robot_clearance_cm": None}, AcquisitionReason.GEOMETRY_INVALID),
            ({"identity": None}, AcquisitionReason.IDENTITY_MISMATCH),
            ({"image_width_px": 0}, AcquisitionReason.GEOMETRY_INVALID),
        ):
            with self.subTest(changes=changes):
                self.acquisition.reset()
                frame = self.frame()
                observation = self.result(frame, **changes)
                self.assertIs(validate_marker_observation(
                    frame, observation, context=self.context, now=0.0,
                ), observation)
                assessment = self.acquisition.observe_frame(frame, observation, now=0.0)
                self.assertEqual(
                    (assessment.status, assessment.reason, assessment.confirmations),
                    (AcquisitionStatus.REJECTED, expected, 0),
                )

    def test_three_distinct_fresh_confirmations_and_boundary_of_oldest_capture(self):
        for final_capture, counts, states in (
            (0.2, (1, 2, 3), (AcquisitionStatus.CONFIRMING,
                             AcquisitionStatus.CONFIRMING, AcquisitionStatus.ACQUIRED)),
            (0.200001, (1, 2, 2), (AcquisitionStatus.CONFIRMING,) * 3),
        ):
            with self.subTest(final_capture=final_capture):
                self.acquisition.reset()
                actual = [self.assess(n, captured)
                          for n, captured in enumerate((0.0, 0.1, final_capture), 1)]
                self.assertEqual(tuple(result.confirmations for result in actual), counts)
                self.assertEqual(tuple(result.status for result in actual), states)
                if final_capture > 0.2:
                    next_result = self.assess(4, 0.21)
                    self.assertEqual(
                        (next_result.status, next_result.confirmations),
                        (AcquisitionStatus.ACQUIRED, 3),
                    )

    def test_delayed_return_uses_original_capture_and_decision_time_for_all_confirmations(self):
        for returned_at, expected in (
            (0.2, (AcquisitionStatus.ACQUIRED, 3)),
            (0.21, (AcquisitionStatus.CONFIRMING, 2)),
            (0.400001, (AcquisitionStatus.REJECTED, 0)),
        ):
            with self.subTest(returned_at=returned_at):
                self.acquisition.reset()
                self.assess(1, 0.0)
                self.assess(2, 0.1)
                frame = self.frame(3, 0.2)
                observation = self.result(frame, published_at=returned_at)
                actual = self.acquisition.observe_frame(frame, observation, now=returned_at)
                self.assertEqual((actual.status, actual.confirmations), expected)
                self.assertEqual(observation.captured_at, 0.2)
                if returned_at > 0.4:
                    self.assertEqual(actual.reason, AcquisitionReason.STALE)

    def test_old_capture_is_not_refreshed_by_new_publication(self):
        for now, expected in ((1.2, AcquisitionStatus.CONFIRMING),
                              (1.200001, AcquisitionStatus.REJECTED)):
            with self.subTest(now=now):
                self.acquisition.reset()
                frame = self.frame(captured=1.0, published_at=1.1)
                observation = self.result(frame, published_at=now)
                assessment = self.acquisition.observe_frame(frame, observation, now=now)
                self.assertEqual(assessment.status, expected)
                if expected is AcquisitionStatus.REJECTED:
                    self.assertEqual(assessment.reason, AcquisitionReason.STALE)

    def test_repeated_and_out_of_order_returns_do_not_count_as_new_confirmations(self):
        self.assess(1, 0.0)
        frame = self.frame(1, 0.0)
        repeated = self.acquisition.observe_frame(
            frame, self.result(frame, published_at=0.01), now=0.01,
        )
        self.assertEqual(
            (repeated.reason, repeated.confirmations), (AcquisitionReason.DUPLICATE_FRAME, 0),
        )
        self.assertEqual(self.assess(2, 0.02).confirmations, 1)
        old = self.acquisition.observe_frame(frame, self.result(frame), now=0.03)
        self.assertEqual(
            (old.reason, old.confirmations), (AcquisitionReason.FRAME_OUT_OF_ORDER, 0),
        )
        gap = self.assess(4, 0.04)
        self.assertEqual((gap.reason, gap.confirmations), (AcquisitionReason.FRAME_GAP, 0))

    def test_matching_results_from_changed_or_old_streams_invalidate_acquisition(self):
        for coordinate in ("source_id", "stream_generation"):
            with self.subTest(coordinate=coordinate):
                self.acquisition.reset()
                for n in range(1, 4):
                    self.assess(n, n * 0.01)
                frame = self.frame(4, 0.04, **{coordinate: "new-stream-coordinate"})
                changed = self.acquisition.observe_frame(frame, self.result(frame), now=0.04)
                self.assertEqual(
                    (changed.reason, changed.confirmations), (AcquisitionReason.STREAM_CHANGED, 0),
                )
                next_frame = self.frame(5, 0.05, **{coordinate: "new-stream-coordinate"})
                confirming = self.acquisition.observe_frame(next_frame, self.result(next_frame), now=0.05)
                self.assertEqual(
                    (confirming.status, confirming.confirmations), (AcquisitionStatus.CONFIRMING, 1),
                )
                old = self.assess(6, 0.06)
                self.assertEqual(
                    (old.reason, old.confirmations), (AcquisitionReason.STREAM_CHANGED, 0),
                )

    def test_all_negative_dispositions_pass_to_acquisition_with_explicit_reasons(self):
        for disposition, reason in (
            (ObservationDisposition.ABSENT, AcquisitionReason.OBSERVATION_ABSENT),
            (ObservationDisposition.AMBIGUOUS, AcquisitionReason.OBSERVATION_AMBIGUOUS),
            (ObservationDisposition.REJECTED, AcquisitionReason.OBSERVATION_REJECTED),
            (ObservationDisposition.FAULT, AcquisitionReason.PERCEPTION_FAULT),
            (ObservationDisposition.STALE, AcquisitionReason.STALE),
        ):
            with self.subTest(disposition=disposition):
                self.acquisition.reset()
                for n in range(1, 4):
                    self.assess(n, n * 0.01)
                actual = self.assess(
                    4, 0.04, disposition=disposition, reason="synthetic-negative",
                    identity=None, quality=None, robot_clearance_cm=None,
                )
                self.assertEqual(
                    (actual.status, actual.reason, actual.confirmations, actual.detail),
                    (AcquisitionStatus.REJECTED, reason, 0, "synthetic-negative"),
                )
                fresh = self.assess(5, 0.05)
                self.assertEqual(
                    (fresh.status, fresh.confirmations), (AcquisitionStatus.CONFIRMING, 1),
                )

    def test_boundary_errors_clear_confirmations_and_acquired_continuity(self):
        for changes in (
            {"source_id": "other-source"}, {"context_version": "old-context"},
            {"frame_number": 3}, {"captured_at": 0.035}, {"disposition": []},
        ):
            with self.subTest(changes=changes):
                self.acquisition.reset()
                for n in range(1, 4):
                    self.assess(n, n * 0.01)
                frame = self.frame(4, 0.04)
                with self.assertRaises(ValueError):
                    self.acquisition.observe_frame(frame, self.result(frame, **changes), now=0.04)
                fresh = self.acquisition.observe_frame(frame, self.result(frame), now=0.04)
                self.assertEqual(
                    (fresh.status, fresh.confirmations), (AcquisitionStatus.CONFIRMING, 1),
                )
                self.assertEqual(self.assess(5, 0.05).confirmations, 2)
                self.assertEqual(self.assess(6, 0.06).status, AcquisitionStatus.ACQUIRED)

    def test_valid_fresh_continuity_remains_acquired_after_initial_captures_expire(self):
        for n in range(1, 4):
            self.assess(n, n * 0.01)
        for n, captured in ((4, 0.2), (5, 0.4), (6, 0.6)):
            actual = self.assess(n, captured)
            self.assertEqual(
                (actual.status, actual.reason, actual.confirmations),
                (AcquisitionStatus.ACQUIRED, AcquisitionReason.ACQUIRED, 3),
            )

    def test_delayed_result_for_previous_context_cannot_confirm_a_new_acquisition(self):
        frame = self.frame(captured=1.0)
        delayed = self.result(frame, published_at=1.1)
        resumed = replace(self.context, context_version="resumed-context")
        acquisition = resumed.new_acquisition(max_age_seconds=0.2)
        with self.assertRaisesRegex(ValueError, "context_version"):
            validate_marker_observation(frame, delayed, context=resumed, now=1.1)
        with self.assertRaisesRegex(ValueError, "context_version"):
            acquisition.observe_frame(frame, delayed, now=1.1)
        fresh = self.provider.observe(frame, context=resumed)
        assessment = acquisition.observe_frame(frame, fresh, now=1.1)
        self.assertEqual(
            (assessment.status, assessment.confirmations), (AcquisitionStatus.CONFIRMING, 1),
        )


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

    def test_malformed_dispositions_are_explicit_rejections_and_clear_confirmations(self):
        for disposition in ("absent", [], {}, None, True):
            with self.subTest(disposition=disposition):
                self.acquisition.reset()
                self.acquisition.observe(self.observation(1), now=0.02)
                result = self.acquisition.observe(
                    self.observation(2, disposition=disposition), now=0.03,
                )
                self.assertEqual(
                    (result.status, result.reason, result.confirmations),
                    (AcquisitionStatus.REJECTED, AcquisitionReason.OBSERVATION_REJECTED, 0),
                )
                fresh = self.acquisition.observe(self.observation(3), now=0.04)
                self.assertEqual(fresh.confirmations, 1)

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
