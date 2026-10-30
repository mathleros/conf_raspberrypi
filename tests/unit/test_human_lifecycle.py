from __future__ import annotations

from dataclasses import replace
import unittest

from irobot.config.settings import MarkerIdentity, RuntimeSettings
from irobot.interfaces.human_lifecycle import (
    AcquisitionMode,
    HumanFollowLifecycle,
    HumanFollowPhase,
)
from irobot.interfaces.human_perception import (
    AcquisitionAssessment,
    AcquisitionReason,
    AcquisitionStatus,
    HumanMarkerMissionContext,
)
from irobot.interfaces.protection import HumanConditions


class HumanFollowLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.context = HumanMarkerMissionContext.from_runtime_settings(
            RuntimeSettings(
                human_marker_identity=MarkerIdentity("aruco", "dictionary-unselected", "unselected"),
            ),
            mission_id="mission-1",
            context_version="context-1",
        )
        self.lifecycle = HumanFollowLifecycle()

    @staticmethod
    def valid_conditions():
        return HumanConditions(
            request_valid=True,
            configuration_qualified=True,
            terrain_checked=True,
            safe_access_demonstrated=True,
            protections_qualified=True,
            camera_context_valid=True,
            marker_acquired=True,
            identity_valid=True,
            observations_fresh=True,
            distance_valid=True,
            obstacle_clear=True,
            swept_volume_protected=True,
            input_audio_ready=True,
            output_audio_ready=True,
            journal_ready=True,
            movement_allowed=True,
            limits_valid=True,
        )

    @staticmethod
    def acquired():
        return AcquisitionAssessment(
            AcquisitionStatus.ACQUIRED,
            AcquisitionReason.ACQUIRED,
            3,
        )

    @staticmethod
    def confirming():
        return AcquisitionAssessment(
            AcquisitionStatus.CONFIRMING,
            AcquisitionReason.WAITING_FOR_CONFIRMATIONS,
            2,
        )

    def begin_and_acquire(self):
        self.lifecycle.begin(self.context, now=0.0)
        self.lifecycle.record_acquisition(self.acquired(), now=1.0)

    def test_initial_acquisition_requires_confirmation_before_activation(self):
        self.lifecycle.begin(self.context, now=2.0)
        pending = self.lifecycle.record_acquisition(self.confirming(), now=3.0)
        self.assertEqual(pending.snapshot.phase, HumanFollowPhase.ACQUIRING)
        acquired = self.lifecycle.record_acquisition(self.acquired(), now=4.0)
        self.assertEqual(acquired.snapshot.phase, HumanFollowPhase.ACQUIRED)
        with self.assertRaises(ValueError):
            self.lifecycle.activate_after_announcement(
                now=4.0,
                conditions=self.valid_conditions(),
            )

        active = self.lifecycle.activate_after_announcement(
            now=4.0,
            mission_deadline=64.0,
            conditions=self.valid_conditions(),
        )
        self.assertEqual(active.snapshot.phase, HumanFollowPhase.ACTIVE)
        self.assertEqual(active.snapshot.mission_deadline, 64.0)

    def test_initial_acquisition_timeout_ends_attempt_and_clears_context(self):
        self.lifecycle.begin(self.context, now=0.0)
        transition = self.lifecycle.record_acquisition(self.confirming(), now=10.0)
        self.assertEqual(transition.outcome, "initial_acquisition_timeout")
        self.assertEqual(transition.ended_mission_id, "mission-1")
        self.assertEqual(transition.snapshot.phase, HumanFollowPhase.AVAILABLE)
        self.assertIsNone(transition.snapshot.context)

    def test_suspend_retains_identity_deadline_and_all_causes(self):
        self.begin_and_acquire()
        self.lifecycle.activate_after_announcement(
            now=1.0,
            mission_deadline=61.0,
            conditions=self.valid_conditions(),
        )
        self.lifecycle.suspend("marker_lost", now=2.0)
        suspended = self.lifecycle.suspend("obstacle", now=2.1)

        self.assertEqual(suspended.snapshot.phase, HumanFollowPhase.SUSPENDED)
        self.assertEqual(suspended.snapshot.context, self.context)
        self.assertEqual(suspended.snapshot.mission_deadline, 61.0)
        self.assertEqual(suspended.snapshot.causes, ("marker_lost", "obstacle"))

    def test_resume_is_explicit_reacquires_same_context_and_keeps_deadline(self):
        self.begin_and_acquire()
        original = self.lifecycle.activate_after_announcement(
            now=1.0,
            mission_deadline=61.0,
            conditions=self.valid_conditions(),
        )
        self.lifecycle.suspend("marker_lost", now=2.0)
        with self.assertRaises(RuntimeError):
            self.lifecycle.request_resume(now=3.0)

        self.lifecycle.resolve_cause("marker_lost")
        reacquiring = self.lifecycle.request_resume(now=3.0)
        self.assertEqual(reacquiring.snapshot.acquisition_mode, AcquisitionMode.RESUME)
        self.assertEqual(reacquiring.snapshot.acquisition_deadline, 13.0)
        self.assertEqual(reacquiring.snapshot.context, self.context)
        self.lifecycle.record_acquisition(self.acquired(), now=4.0)
        resumed = self.lifecycle.activate_after_announcement(
            now=4.0,
            conditions=self.valid_conditions(),
        )
        self.assertEqual(resumed.snapshot.phase, HumanFollowPhase.ACTIVE)
        self.assertEqual(resumed.snapshot.mission_deadline, original.snapshot.mission_deadline)

    def test_failed_reacquisition_returns_to_suspension_without_retry(self):
        self.begin_and_acquire()
        self.lifecycle.activate_after_announcement(
            now=1.0,
            mission_deadline=61.0,
            conditions=self.valid_conditions(),
        )
        self.lifecycle.suspend("marker_lost", now=2.0)
        self.lifecycle.resolve_cause("marker_lost")
        self.lifecycle.request_resume(now=3.0)

        failed = self.lifecycle.record_acquisition(self.confirming(), now=13.0)
        self.assertEqual(failed.outcome, "reacquisition_timeout")
        self.assertEqual(failed.snapshot.phase, HumanFollowPhase.SUSPENDED)
        self.assertEqual(failed.snapshot.causes, ("reacquisition_timeout",))
        self.assertEqual(failed.snapshot.mission_deadline, 61.0)

    def test_expire_enforces_acquisition_timeout_without_a_new_observation(self):
        self.lifecycle.begin(self.context, now=0.0)
        transition = self.lifecycle.expire(now=10.0)
        self.assertEqual(transition.outcome, "initial_acquisition_timeout")
        self.assertEqual(transition.snapshot.phase, HumanFollowPhase.AVAILABLE)

    def test_mission_deadline_terminates_suspended_session(self):
        self.begin_and_acquire()
        self.lifecycle.activate_after_announcement(
            now=1.0,
            mission_deadline=61.0,
            conditions=self.valid_conditions(),
        )
        self.lifecycle.suspend("marker_lost", now=2.0)

        expired = self.lifecycle.expire(now=61.0)
        self.assertEqual(expired.outcome, "deadline")
        self.assertEqual(expired.snapshot.phase, HumanFollowPhase.AVAILABLE)
        self.assertIsNone(expired.snapshot.context)

    def test_hold_never_selects_motion_or_resumes_without_explicit_call(self):
        self.begin_and_acquire()
        self.lifecycle.activate_after_announcement(
            now=1.0,
            mission_deadline=61.0,
            conditions=self.valid_conditions(),
        )
        held = self.lifecycle.hold(now=2.0)

        self.assertEqual(held.snapshot.phase, HumanFollowPhase.HOLDING)
        self.assertFalse(hasattr(held, "command"))
        with self.assertRaises(RuntimeError):
            self.lifecycle.request_resume(now=2.0)
        self.assertEqual(
            self.lifecycle.continue_tracking(
                now=3.0, conditions=self.valid_conditions(),
            ).snapshot.phase,
            HumanFollowPhase.ACTIVE,
        )

    def test_preconditions_block_activation_and_suspend_held_session(self):
        self.begin_and_acquire()
        unsafe_conditions = replace(self.valid_conditions(), protections_qualified=False)
        with self.assertRaisesRegex(RuntimeError, "protections_qualified"):
            self.lifecycle.activate_after_announcement(
                now=1.0,
                mission_deadline=61.0,
                conditions=unsafe_conditions,
            )
        self.assertEqual(self.lifecycle.snapshot.phase, HumanFollowPhase.ACQUIRED)

        self.lifecycle.activate_after_announcement(
            now=1.0,
            mission_deadline=61.0,
            conditions=self.valid_conditions(),
        )
        self.lifecycle.hold(now=2.0)
        suspended = self.lifecycle.continue_tracking(
            now=3.0,
            conditions=unsafe_conditions,
        )
        self.assertEqual(suspended.snapshot.phase, HumanFollowPhase.SUSPENDED)
        self.assertEqual(suspended.snapshot.causes, ("protections_qualified",))

    def test_finish_clears_context_and_allows_a_new_mission(self):
        self.lifecycle.begin(self.context, now=0.0)
        finished = self.lifecycle.finish("cancelled")
        self.assertEqual(finished.outcome, "cancelled")
        self.assertEqual(finished.snapshot, self.lifecycle.snapshot)
        self.assertEqual(finished.snapshot.phase, HumanFollowPhase.AVAILABLE)
        next_context = HumanMarkerMissionContext(
            "mission-2", "context-2", self.context.identity,
        )
        self.assertEqual(
            self.lifecycle.begin(next_context, now=1.0).snapshot.context,
            next_context,
        )

    def test_monotonic_time_regression_is_rejected(self):
        self.lifecycle.begin(self.context, now=5.0)
        with self.assertRaises(ValueError):
            self.lifecycle.expire(now=4.0)


if __name__ == "__main__":
    unittest.main()
