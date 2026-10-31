"""Structured replays only; imported after the isolated runner's guards."""

from dataclasses import replace
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from irobot.config.settings import MarkerIdentity, RuntimeSettings
from irobot.interfaces.human_follow_runtime import HumanFollowRequest
from irobot.interfaces.human_lifecycle import HumanFollowPhase
from irobot.interfaces.human_perception import MarkerObservation, MarkerQuality, ObservationDisposition
from irobot.interfaces.protection import HumanConditions, ProtectionFault
from irobot.interfaces import voice_runtime as vr
from tests.isolated.lot_a_cases import (
    FollowObjectSkill, REQUIRED_HUMAN_CONDITIONS, Rig, SyntheticSkill, nonzero, unexpected_llm,
)


class HumanFollowRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.rig = Rig()
        self.runtime = self.rig.runtime(self.directory.name)
        self.identity = MarkerIdentity("synthetic-family", "synthetic-dictionary", "synthetic-id")
        self.runtime.settings = RuntimeSettings(human_marker_identity=self.identity)
        self.frame = 0

    def prepare(self, **changes):
        options = dict(
            conditions=self.rig.conditions, journal=self.rig.witness,
            max_age_seconds=0.2, announcement_timeout_seconds=2.0,
        )
        options.update(changes)
        return self.runtime.prepare_human_follow(HumanFollowRequest(), **options)

    def step(self, seconds=0.01):
        self.rig.clock.now += seconds
        self.rig.p5.refresh()

    def observation(self, **changes):
        context = self.runtime.human_follow_snapshot.context
        self.frame += 1
        return replace(MarkerObservation(
            source_id="synthetic-camera", stream_generation="synthetic-stream",
            frame_number=self.frame, captured_at=self.rig.clock.now,
            published_at=self.rig.clock.now, mission_id=context.mission_id,
            context_version=context.context_version, disposition=ObservationDisposition.VALID,
            identity=self.identity, image_width_px=640, image_height_px=480,
            center_x_px=320.0, center_y_px=240.0, bearing_deg=0.0,
            optical_distance_cm=160.0, robot_clearance_cm=150.0,
            calibration_version="synthetic-calibration",
            quality=MarkerQuality(True, True),
        ), **changes)

    def acquire(self):
        for _ in range(3):
            self.step()
            result = self.runtime.advance_human_follow(observation=self.observation())
        self.assertEqual(result["status"], "acquired")
        return self.runtime.pending_human_announcement

    def activate(self):
        self.assertEqual(self.prepare()["status"], "acquiring")
        announcement = self.acquire()
        result = self.runtime.advance_human_follow(completed_announcement=announcement.token)
        self.assertEqual(result["status"], "active")
        return self.runtime.human_follow_snapshot

    def test_reserves_before_acquisition_with_no_mission_deadline_or_output(self):
        result = self.prepare()
        self.assertEqual(result["status"], "acquiring")
        self.assertTrue(self.runtime.mission_running())
        self.assertIsNone(self.rig.robot.reservation.deadline)
        self.assertEqual(self.rig.robot.reservation.phase, "acquiring")
        self.assertEqual(self.prepare()["reason"], "mission_reserved")
        self.assertEqual(self.runtime.handle_text_as_plan("avance")["reason"], "mission_reserved")
        self.assertFalse(nonzero(self.rig.motor))

    def test_acquisition_does_not_skip_nonperception_preconditions(self):
        pending = {"marker_acquired", "identity_valid", "observations_fresh", "distance_valid"}
        for name in REQUIRED_HUMAN_CONDITIONS:
            if name in pending:
                continue
            with self.subTest(condition=name):
                self.rig.facts = replace(self.rig.facts, **{name: False})
                self.assertIn(name, self.prepare()["reason"])
                self.assertIsNone(self.rig.robot.reservation)
                self.rig.facts = replace(self.rig.facts, **{name: True})
        self.assertFalse(nonzero(self.rig.motor))

    def test_marker_configuration_missing_refuses_without_reserving(self):
        self.runtime.settings = RuntimeSettings()
        self.assertEqual(self.prepare()["reason"], "human_marker_not_configured")
        self.assertIsNone(self.rig.robot.reservation)

    def test_configuration_is_snapshotted_not_adopted_from_observation(self):
        self.prepare()
        original = self.runtime.human_follow_snapshot.context
        self.runtime.settings = RuntimeSettings(
            human_marker_identity=MarkerIdentity("different", "different", "different"),
        )
        self.acquire()
        self.assertEqual(self.runtime.human_follow_snapshot.context, original)
        self.assertEqual(original.identity, self.identity)

    def test_acquisition_and_announcement_never_authorize_l2_outputs(self):
        self.prepare()
        permit = self.rig.robot.reservation.permit
        for command in ("forward", "left", "right", "set_speed"):
            with self.subTest(command=command):
                with self.assertRaises(ProtectionFault):
                    self.rig.robot.supervise(permit, command, 0.1)
        self.acquire()
        with self.assertRaises(ProtectionFault):
            self.rig.robot.bind(permit).forward()
        self.assertFalse(nonzero(self.rig.motor))

    def test_duration_begins_after_announcement_and_no_skill_is_available(self):
        self.prepare()
        announcement = self.acquire()
        self.step(0.1)
        result = self.runtime.advance_human_follow(completed_announcement=announcement.token)
        self.assertEqual(result["status"], "active")
        self.assertAlmostEqual(self.rig.robot.reservation.deadline, self.rig.clock.now + 60.0)
        self.assertEqual(
            self.runtime.execute_reserved_skill(
                self.rig.robot.reservation.permit, SyntheticSkill(self.rig),
            )["reason"], "human_motion_provider_unavailable",
        )
        self.assertFalse(nonzero(self.rig.motor))

    def test_stale_observation_during_announcement_prevents_activation(self):
        self.prepare()
        token = self.acquire().token
        self.step(0.201)
        self.assertEqual(
            self.runtime.advance_human_follow(completed_announcement=token)["status"],
            "available",
        )
        self.assertIsNone(self.rig.robot.reservation)
        self.assertIsNone(self.runtime.human_follow_snapshot)
        self.assertFalse(nonzero(self.rig.motor))

    def test_old_announcement_completion_never_activates(self):
        self.prepare()
        old_token = self.runtime.pending_human_announcement.token
        self.acquire()
        self.assertEqual(
            self.runtime.advance_human_follow(completed_announcement=old_token)["reason"],
            "obsolete_announcement",
        )
        self.assertEqual(self.rig.robot.reservation.phase, "acquiring")
        self.assertFalse(nonzero(self.rig.motor))

    def test_initial_acquisition_timeout_is_exact_without_new_observation(self):
        self.prepare(announcement_timeout_seconds=20.0)
        self.step(9.999)
        self.runtime.supervise_once()
        self.assertTrue(self.runtime.mission_running())
        self.step(0.001)
        self.runtime.supervise_once()
        self.assertFalse(self.runtime.mission_running())
        self.assertIsNone(self.runtime.human_follow_snapshot)

    def test_initial_announcement_timeout_does_not_activate(self):
        self.prepare()
        announcement = self.acquire()
        self.rig.clock.now = announcement.deadline
        self.rig.p5.refresh()
        self.runtime.supervise_once()
        self.assertIsNone(self.rig.robot.reservation)
        self.assertIsNone(self.runtime.pending_human_announcement)
        self.assertIn("announcement_timeout", self.rig.robot.causes)
        self.assertFalse(nonzero(self.rig.motor))

    def test_stop_in_acquisition_and_announcement_is_local_and_cleans_context(self):
        for acquired in (False, True):
            with self.subTest(acquired=acquired):
                self.prepare()
                if acquired:
                    self.acquire()
                with patch.object(vr, "ask_llm_for_intent_plan_with_trace", unexpected_llm):
                    result = self.runtime.handle_text_as_plan("stop")
                self.assertEqual(result["status"], "available")
                self.assertIsNone(self.runtime.human_follow_snapshot)
                self.assertIsNone(self.rig.robot.reservation)
                self.assertEqual(
                    self.runtime.handle_text_as_plan("reprends le suivi")["reason"],
                    "no_resumable_session",
                )
        self.assertFalse(nonzero(self.rig.motor))

    def test_suspend_reappear_resume_reacquires_new_context_same_identity_and_deadline(self):
        original = self.activate()
        old_observation = self.observation()
        self.runtime.advance_human_follow(events=("obstacle",))
        self.assertEqual(self.runtime.human_follow_snapshot.phase, HumanFollowPhase.SUSPENDED)
        self.step()
        self.runtime.advance_human_follow(observation=old_observation)
        self.assertEqual(self.runtime.human_follow_snapshot.phase, HumanFollowPhase.SUSPENDED)
        with patch.object(vr, "ask_llm_for_intent_plan_with_trace", unexpected_llm):
            result = self.runtime.handle_text_as_plan("reprenez le suivi")
        self.assertEqual(result["status"], "acquiring")
        context = self.runtime.human_follow_snapshot.context
        self.assertEqual(context.identity, original.context.identity)
        self.assertEqual(context.mission_id, original.context.mission_id)
        self.assertNotEqual(context.context_version, original.context.context_version)
        self.runtime.advance_human_follow(observation=old_observation)
        self.assertEqual(self.runtime.human_follow_snapshot.last_acquisition_reason, "context_mismatch")
        announcement = self.acquire()
        self.assertEqual(announcement.template, "resume")
        self.assertLess(announcement.remaining_s, 60.0)
        self.runtime.advance_human_follow(completed_announcement=announcement.token)
        self.assertEqual(self.runtime.human_follow_snapshot.mission_deadline, original.mission_deadline)
        self.assertFalse(nonzero(self.rig.motor))

    def test_resume_requires_all_nonperception_conditions_and_no_request_is_queued(self):
        self.activate()
        self.rig.facts = replace(self.rig.facts, obstacle_clear=False)
        self.runtime.supervise_once()
        self.assertIn(
            "obstacle_clear", self.runtime.handle_text_as_plan("reprends le suivi")["reason"],
        )
        self.rig.facts = replace(self.rig.facts, obstacle_clear=True)
        self.runtime.supervise_once()
        self.assertEqual(self.runtime.human_follow_snapshot.phase, HumanFollowPhase.SUSPENDED)

    def test_reacquisition_timeout_retains_reservation_and_original_deadline(self):
        original = self.activate()
        self.runtime.advance_human_follow(events=("obstacle",))
        self.runtime.handle_text_as_plan("reprends le suivi")
        self.step(10.0)
        self.runtime.supervise_once()
        self.assertEqual(self.runtime.human_follow_snapshot.phase, HumanFollowPhase.SUSPENDED)
        self.assertEqual(self.rig.robot.reservation.deadline, original.mission_deadline)
        self.assertIn("reacquisition_timeout", self.rig.robot.causes)

    def test_deadline_during_resume_announcement_wins_over_completion(self):
        original = self.activate()
        self.runtime.advance_human_follow(events=("obstacle",))
        self.rig.clock.now = original.mission_deadline - 0.1
        self.rig.p5.refresh()
        self.runtime.handle_text_as_plan("reprends le suivi")
        announcement = self.acquire()
        self.rig.clock.now = original.mission_deadline
        self.rig.p5.refresh()
        result = self.runtime.advance_human_follow(completed_announcement=announcement.token)
        self.assertEqual(result["status"], "available")
        self.assertIsNone(self.rig.robot.reservation)
        self.assertIn("deadline", result["causes"])
        self.assertFalse(nonzero(self.rig.motor))

    def test_hold_denies_all_nonzero_commands_and_keeps_deadline(self):
        original = self.activate()
        self.runtime.advance_human_follow(holding=True)
        permit = self.rig.robot.reservation.permit
        for command in ("forward", "left", "right", "set_speed"):
            with self.subTest(command=command):
                with self.assertRaises(ProtectionFault):
                    self.rig.robot.supervise(permit, command, 0.1)
        self.runtime.advance_human_follow(holding=False)
        self.assertEqual(self.runtime.human_follow_snapshot.phase, HumanFollowPhase.ACTIVE)
        self.assertEqual(self.rig.robot.reservation.deadline, original.mission_deadline)
        self.assertFalse(nonzero(self.rig.motor))

    def test_p1_stop_deadline_simultaneous_never_reports_active_or_resumable(self):
        original = self.activate()
        self.rig.clock.now = original.mission_deadline
        self.rig.p5.refresh()
        result = self.runtime.advance_human_follow(events=("P6", "stop", "obstacle"))
        self.assertEqual(result["status"], "available")
        self.assertTrue({"P6", "stop", "deadline", "obstacle"} <= set(result["causes"]))
        self.assertEqual(set(self.rig.witness.requests[-1].split("+")), {"P6", "stop", "obstacle"})
        self.assertEqual(self.prepare()["reason"], "rearm_required")
        self.assertIsNone(self.runtime.human_follow_snapshot)

    def test_p5_reading_is_not_refreshed_by_preparation(self):
        self.prepare(announcement_timeout_seconds=20.0)
        self.rig.clock.now += 0.251
        self.runtime.supervise_once()
        self.assertIsNone(self.rig.robot.reservation)
        self.assertIn("p5_stale", self.rig.robot.causes)
        self.assertFalse(nonzero(self.rig.motor))

    def test_journal_failure_stops_and_cannot_leave_activatable_token(self):
        self.prepare()
        self.acquire()
        self.rig.witness.fail_journal = True
        result = self.runtime.advance_human_follow(observation=self.observation())
        self.assertEqual(result["status"], "rejected")
        self.assertIsNone(self.runtime.pending_human_announcement)
        self.assertIsNone(self.rig.robot.reservation)
        self.assertFalse(nonzero(self.rig.motor))

    def test_structured_journal_failure_in_session_is_explicit_and_suspended(self):
        self.activate()

        class BrokenJournal:
            def write(self, event):
                raise OSError("scripted structured journal failure")

        self.runtime._human_follow._journal = BrokenJournal()
        cycles = len(self.rig.witness.cycles)
        result = self.runtime.advance_human_follow(observation=self.observation())
        self.assertEqual(result["reason"], "journal_error")
        self.assertEqual(self.runtime.human_follow_snapshot.phase, HumanFollowPhase.SUSPENDED)
        self.assertEqual(self.rig.motor.commands[-1], "stop")
        self.assertIsNone(self.runtime.pending_human_announcement)
        self.assertEqual(len(self.rig.witness.cycles), cycles)

    def test_human_requests_remain_refused_in_all_language_entries(self):
        self.prepare()
        for entry in (self.runtime.handle_text, self.runtime.handle_text_as_plan,
                      self.runtime.handle_transcript):
            with self.subTest(entry=entry.__name__):
                self.assertEqual(entry("suis-moi")["reason"], "human_capability_unavailable")
        self.assertFalse(nonzero(self.rig.motor))

    def test_ball_human_preparation_ball_same_runtime_no_inherited_context(self):
        perception = SimpleNamespace(detect=lambda **_: SimpleNamespace(
            position="center", distance_cm=40.0, label="yellow", confidence=1.0,
        ))
        self.runtime.controller.perception = perception
        self.runtime.controller.planner.registry.register(FollowObjectSkill(
            settings=RuntimeSettings(),
            time_fn=self.rig.clock.time, sleep_fn=self.rig.clock.sleep,
        ))
        with patch.object(vr, "ask_llm_for_intent_plan_with_trace", unexpected_llm):
            self.assertEqual(
                self.runtime.handle_text_as_plan("suis la balle jaune pendant 1 seconde")["status"],
                "accepted",
            )
            self.assertIn("backward", nonzero(self.rig.motor))
            self.activate()
            self.runtime.handle_text_as_plan("stop")
            self.rig.motor.commands.clear()
            self.assertEqual(
                self.runtime.handle_text_as_plan("suis la balle jaune pendant 1 seconde")["status"],
                "accepted",
            )
            self.assertIn("backward", nonzero(self.rig.motor))
        self.assertIsNone(self.runtime.human_follow_snapshot)
        self.assertIsNone(self.runtime._reserved_context)

    def test_trace_has_ordered_decisions_without_raw_media_or_text(self):
        self.activate()
        self.runtime.handle_text_as_plan("stop")
        events = [event for event in self.rig.witness.journal
                  if event.get("schema") == "human-follow/1"]
        self.assertEqual([event["sequence"] for event in events], list(range(1, len(events) + 1)))
        self.assertIn("activated", [event["event"] for event in events])
        self.assertEqual(events[-1]["event"], "ended")
        forbidden = {"raw_text", "prompt", "llm_content", "image", "audio", "physically_stopped"}
        self.assertTrue(all(not forbidden.intersection(event) for event in events))

    def test_suspended_perception_cannot_bypass_reacquisition_via_controller_resume(self):
        self.activate()
        self.runtime.advance_human_follow(events=("obstacle",))
        with self.assertRaises(ProtectionFault):
            self.rig.robot.resume()
        self.assertEqual(self.rig.robot.reservation.phase, "suspended")
        self.assertFalse(nonzero(self.rig.motor))

    def test_each_external_precondition_loss_stops_without_an_automatic_restart(self):
        derived = {"marker_acquired", "identity_valid", "observations_fresh", "distance_valid"}
        self.activate()
        for name in REQUIRED_HUMAN_CONDITIONS:
            if name in derived:
                continue
            with self.subTest(condition=name):
                self.rig.facts = replace(self.rig.facts, **{name: False})
                self.runtime.supervise_once()
                self.assertEqual(self.runtime.human_follow_snapshot.phase, HumanFollowPhase.SUSPENDED)
                self.assertIn(name, self.rig.robot.causes)
                self.assertEqual(self.rig.motor.commands[-1], "stop")
                self.rig.facts = replace(self.rig.facts, **{name: True})
                self.runtime.supervise_once()
                self.assertEqual(self.runtime.human_follow_snapshot.phase, HumanFollowPhase.SUSPENDED)
                self.runtime.handle_text_as_plan("reprends le suivi")
                announcement = self.acquire()
                self.runtime.advance_human_follow(completed_announcement=announcement.token)
                self.assertEqual(self.runtime.human_follow_snapshot.phase, HumanFollowPhase.ACTIVE)
        self.assertFalse(nonzero(self.rig.motor))

    def test_resume_deadline_cannot_be_changed_by_controller_activation(self):
        original = self.activate()
        self.runtime.advance_human_follow(events=("obstacle",))
        self.runtime.handle_text_as_plan("reprends le suivi")
        self.acquire()
        with self.assertRaisesRegex(ProtectionFault, "deadline_unchangeable"):
            self.rig.robot.activate_human(
                self.rig.robot.reservation.permit, deadline=original.mission_deadline + 1,
            )
        self.assertEqual(self.rig.robot.reservation.deadline, original.mission_deadline)

    def test_confirmation_with_stop_does_not_prepare_an_activation_message(self):
        self.prepare()
        for _ in range(2):
            self.step()
            self.runtime.advance_human_follow(observation=self.observation())
        self.step()
        result = self.runtime.advance_human_follow(
            events=("stop",), observation=self.observation(),
        )
        self.assertEqual(result["status"], "available")
        self.assertIsNone(self.runtime.pending_human_announcement)
        self.assertNotIn(
            "activate", [event.get("template") for event in self.rig.witness.journal],
        )
        self.assertFalse(nonzero(self.rig.motor))

    def test_malformed_observation_is_explicit_locks_and_cleans_session(self):
        self.prepare()
        with self.assertRaises(TypeError):
            self.runtime.advance_human_follow(observation=object())
        self.assertIsNone(self.rig.robot.reservation)
        self.assertIsNone(self.runtime.human_follow_snapshot)
        self.assertEqual(self.rig.motor.commands[-1], "stop")
        self.assertEqual(self.prepare()["reason"], "rearm_required")

    def test_no_proof_without_an_evaluated_cycle(self):
        self.prepare()
        before = len(self.rig.witness.cycles)
        self.runtime.pending_human_announcement
        self.runtime.human_follow_snapshot
        self.assertEqual(len(self.rig.witness.cycles), before)
        self.runtime.supervise_once()
        self.assertGreater(len(self.rig.witness.cycles), before)
        self.assertEqual(len(self.rig.witness.cycles), len(set(self.rig.witness.cycles)))

    def test_prior_armament_observation_request_is_refused_not_saved(self):
        self.activate()
        self.runtime.advance_human_follow(events=("P6",))
        self.step()
        self.rig.p5.transition("inhibited", "after-P6", "P6")
        self.runtime.supervise_once()
        self.step()
        self.rig.p5.transition("armed", "after-manual-rearm")
        self.assertEqual(self.prepare()["reason"], "rearm_required")
        self.assertIsNone(self.rig.robot.reservation)
        self.assertFalse(nonzero(self.rig.motor))
        self.assertEqual(self.prepare()["status"], "acquiring")

    def test_structured_preparation_is_not_enabled_on_threaded_runtime(self):
        self.runtime.threaded = True
        self.assertEqual(
            self.prepare()["reason"], "human_preparation_requires_synchronous_runtime",
        )
        self.assertIsNone(self.rig.robot.reservation)

    def test_old_completion_after_stop_and_new_session_is_rejected(self):
        self.prepare()
        previous = self.acquire().token
        self.runtime.handle_text_as_plan("stop")
        self.prepare()
        current = self.acquire().token
        self.assertNotEqual(previous, current)
        self.assertEqual(
            self.runtime.advance_human_follow(completed_announcement=previous)["reason"],
            "obsolete_announcement",
        )
        self.assertEqual(self.runtime.human_follow_snapshot.phase, HumanFollowPhase.ACQUIRED)
        self.assertFalse(nonzero(self.rig.motor))

    def test_request_ranges_reject_instead_of_clamping(self):
        for field in ("stand_off_cm", "duration_s"):
            for value in (True, float("nan"), float("inf"), -1, "150", {}):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        HumanFollowRequest(**{field: value})
        for stand_off, duration in ((120, 10), (200, 300)):
            self.assertEqual(HumanFollowRequest(stand_off, duration).stand_off_cm, stand_off)
        for stand_off, duration in ((119.999, 60), (200.001, 60), (150, 9.999), (150, 300.001)):
            with self.assertRaises(ValueError):
                HumanFollowRequest(stand_off, duration)
