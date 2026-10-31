"""SH-05 software contracts; all motion qualifications below are FICTIONAL."""

from dataclasses import replace
from itertools import permutations
import tempfile
import unittest

from irobot.domain.skills.base_skill import Skill, SkillResult
from irobot.config.settings import MarkerIdentity, RuntimeSettings
from irobot.interfaces.human_follow_runtime import HumanFollowRequest, HumanFollowRuntime
from irobot.interfaces.human_perception import (
    MarkerObservation, MarkerQuality, ObservationDisposition,
)
from irobot.interfaces.intent_parser import Intent
from irobot.interfaces.language_controller import LanguageController
from irobot.interfaces.protection import (
    HumanConditions, HumanMotionLimits, ProtectionFault, ProtectionPorts, ProtectionState,
)
from irobot.interfaces.robot_controller import RobotController
from irobot.interfaces.voice_runtime import VoiceRuntime


REQUIRED = (
    "request_valid", "configuration_qualified", "terrain_checked", "safe_access_demonstrated",
    "protections_qualified", "camera_context_valid", "marker_acquired", "identity_valid",
    "observations_fresh", "distance_valid", "obstacle_clear", "swept_volume_protected",
    "input_audio_ready", "output_audio_ready", "journal_ready", "movement_allowed", "limits_valid",
)
FICTIONAL_LIMITS = HumanMotionLimits("FICTIONAL-SH05", 0.6, 0.15, 0.5, 0.1, 0.2)


class Clock:
    def __init__(self):
        self.now = 0.0
        self.on_wait = lambda: None

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        self.on_wait()


class Output:
    """Independent output recorder: never reads the decision journal."""

    def __init__(self, clock):
        self.clock = clock
        self.speed = 0.5
        self.outputs = []
        self.obstacle = False
        self.fail_stop = False

    def forward(self):
        self.outputs.append((self.clock.now, "forward"))

    def backward(self):
        self.outputs.append((self.clock.now, "backward"))

    def left(self):
        self.outputs.append((self.clock.now, "left"))

    def right(self):
        self.outputs.append((self.clock.now, "right"))

    def set_speed(self, speed):
        self.outputs.append((self.clock.now, ("speed", speed)))
        self.speed = speed

    def stop(self):
        if self.fail_stop:
            raise OSError("zero output unavailable")
        self.outputs.append((self.clock.now, "zero"))

    def check_obstacle(self):
        if isinstance(self.obstacle, Exception):
            raise self.obstacle
        return self.obstacle


class Reader:
    def __init__(self, clock):
        self.clock = clock
        self.sample = ProtectionState("inhibited", "boot", 0.0, 0.0, ("startup",))
        self.on_read = lambda: None

    def read(self):
        self.on_read()
        return self.sample

    def refresh(self):
        self.sample = replace(self.sample, observed_at=self.clock.now)


class Proof:
    def __init__(self):
        self.cycles = []
        self.fail = False

    def emit(self, cycle):
        if self.fail:
            raise OSError("proof unavailable")
        self.cycles.append(cycle)


class Inhibition:
    def __init__(self):
        self.requests = []

    def request(self, cause):
        self.requests.append(cause)


class Journal:
    def __init__(self):
        self.entries = []
        self.on_write = lambda event: None

    def write(self, event):
        self.on_write(event)
        self.entries.append(dict(event))


class Rig:
    def __init__(self, limits=FICTIONAL_LIMITS):
        self.clock = Clock()
        self.output = Output(self.clock)
        self.reader = Reader(self.clock)
        self.proof = Proof()
        self.inhibition = Inhibition()
        self.journal = Journal()
        self.facts = HumanConditions(**{name: True for name in REQUIRED})
        self.robot = RobotController(
            self.output, self.clock.time, self.clock.sleep, protection="present",
            ports=ProtectionPorts(self.reader, self.proof, self.inhibition, 0.25, self.journal),
            human_motion_limits=limits,
        )
        self.robot.supervise()
        self.clock.now = 1.0
        self.reader.sample = ProtectionState("armed", "arm-1", 1.0, 1.0)
        self.robot.supervise()
        self.clock.on_wait = self.reader.refresh
        self.output.outputs.clear()

    def human(self):
        return self.robot.admit(human=True, deadline=5.0, conditions=lambda: self.facts)

    def nonzero(self):
        return [item for item in self.output.outputs if item[1] != "zero"]


class ScriptedSkill(Skill):
    def __init__(self, action=lambda context: SkillResult()):
        self.action = action
        self.calls = 0

    def execute(self, context):
        self.calls += 1
        return self.action(context)


class HumanSafetyTests(unittest.TestCase):
    def test_each_precondition_at_admission_and_emission(self):
        for name in REQUIRED:
            for moment in ("admission", "emission"):
                with self.subTest(name=name, moment=moment):
                    rig = Rig()
                    permit = rig.human() if moment == "emission" else None
                    rig.facts = replace(rig.facts, **{name: None})
                    with self.assertRaisesRegex(ProtectionFault, name):
                        if permit is None:
                            rig.human()
                        else:
                            rig.robot.bind(permit).forward()
                    self.assertFalse(rig.nonzero())

    def test_each_precondition_lost_during_motion(self):
        for name in REQUIRED:
            with self.subTest(name=name):
                rig = Rig()
                permit = rig.human()

                def lose():
                    rig.reader.refresh()
                    rig.facts = replace(rig.facts, **{name: False})

                rig.clock.on_wait = lose
                with self.assertRaisesRegex(ProtectionFault, name):
                    rig.robot.bind(permit).forward_for(0.1)
                self.assertEqual(len(rig.nonzero()), 1)
                self.assertEqual(rig.output.outputs[-1][1], "zero")
                self.assertEqual(rig.robot.reservation.phase, "suspended")
                self.assertFalse(rig.robot.valid_result(permit))

    def test_unqualified_motion_is_refused_but_stationary_admission_remains_available(self):
        rig = Rig(None)
        permit = rig.human()
        with self.assertRaisesRegex(ProtectionFault, "human_motion_unqualified"):
            rig.robot.bind(permit).forward()
        rig.robot.bind(permit).set_speed(0)
        self.assertFalse(rig.nonzero())

    def test_speed_setting_bound_is_not_a_ground_speed_conversion(self):
        for speed, allowed in ((0.6, True), (0.600001, False), (-0.1, False),
                               (True, False), (False, False), (0j, False),
                               (float("nan"), False), ("fast", False)):
            with self.subTest(speed=speed):
                rig = Rig()
                permit = rig.human()
                if allowed:
                    rig.robot.bind(permit).set_speed(speed)
                    self.assertEqual(rig.nonzero()[0][1], ("speed", speed))
                else:
                    with self.assertRaisesRegex(ProtectionFault, "human_speed"):
                        rig.robot.bind(permit).set_speed(speed)
                    self.assertFalse(rig.nonzero())
        for speed in (0.150001, float("inf"), True):
            with self.subTest(ground_speed=speed), self.assertRaises(ValueError):
                HumanMotionLimits("FICTIONAL", 0.6, speed)

    def test_driver_setting_is_checked_for_every_direction(self):
        rig = Rig()
        permit = rig.human()
        rig.output.speed = 0.7
        with self.assertRaisesRegex(ProtectionFault, "human_speed"):
            rig.robot.bind(permit).forward()
        self.assertFalse(rig.nonzero())

    def test_no_reversal_or_unbounded_or_unqualified_search_rotation(self):
        for command, limits in (
            ("backward", FICTIONAL_LIMITS), ("left", FICTIONAL_LIMITS),
            ("right", FICTIONAL_LIMITS),
            ("left_for", HumanMotionLimits("FICTIONAL-forward-only", 0.6, 0.1)),
        ):
            with self.subTest(command=command):
                rig = Rig(limits)
                permit = rig.human()
                with self.assertRaisesRegex(ProtectionFault, "human_(backward|rotation)"):
                    method = getattr(rig.robot.bind(permit), command)
                    method(0.1) if command.endswith("_for") else method()
                self.assertFalse(rig.nonzero())

    def test_rotation_exact_duration_and_angle_boundaries(self):
        for direction in ("left_for", "right_for"):
            for duration, angle, allowed in ((0.2, 0.1, True), (0.200001, 0.1, False),
                                            (0.2, 0.099999, False)):
                with self.subTest(direction=direction, duration=duration, angle=angle):
                    rig = Rig(replace(FICTIONAL_LIMITS, max_rotation_angle_rad=angle))
                    permit = rig.human()
                    call = getattr(rig.robot.bind(permit), direction)
                    if allowed:
                        call(duration)
                        self.assertEqual(len(rig.nonzero()), 1)
                        self.assertAlmostEqual(rig.output.outputs[-1][0], 1.2)
                    else:
                        with self.assertRaisesRegex(ProtectionFault, "rotation_outside"):
                            call(duration)
                        self.assertFalse(rig.nonzero())

    def test_invalid_and_zero_durations_never_emit(self):
        for duration in (False, -1, float("nan"), float("inf"), "later", 0):
            with self.subTest(duration=duration):
                rig = Rig()
                permit = rig.human()
                if duration == 0 and duration is not False:
                    rig.robot.bind(permit).forward_for(duration)
                else:
                    with self.assertRaisesRegex(ProtectionFault, "invalid_motion_duration"):
                        rig.robot.bind(permit).forward_for(duration)
                self.assertFalse(rig.nonzero())

    def test_obstacle_read_faults_are_explicit_and_suspend(self):
        for value, cause in ((True, "obstacle"), (None, "obstacle_sensor_unavailable"),
                             ("clear", "obstacle_sensor_incoherent"),
                             (OSError("sensor failed"), "obstacle_sensor_error")):
            with self.subTest(value=value):
                rig = Rig()
                permit = rig.human()
                rig.output.obstacle = value
                with self.assertRaisesRegex(ProtectionFault, cause):
                    rig.robot.bind(permit).forward()
                self.assertIn(cause, rig.robot.causes)
                self.assertEqual(rig.robot.reservation.phase, "suspended")
                self.assertFalse(rig.nonzero())

    def test_stop_input_failure_is_not_disguised_as_a_successful_stop(self):
        for events in ((), ("stop",), ("P6", "stop")):
            with self.subTest(events=events):
                rig = Rig()
                permit = rig.human()

                def broken_input():
                    raise OSError("stop input unavailable")

                rig.output.is_emergency_stop_requested = broken_input
                if events:
                    rig.robot.supervise(events=events)
                else:
                    with self.assertRaisesRegex(ProtectionFault, "stop_input_error"):
                        rig.robot.bind(permit).forward()
                self.assertIn("stop_input_error", rig.robot.causes)
                self.assertEqual(rig.robot.reservation.phase,
                                 "locked" if "P6" in events else "ended" if events else "suspended")
                self.assertFalse(rig.nonzero())

    def test_stop_and_priority_one_deliver_zero_before_any_p5_read(self):
        for events in (("stop",), ("cancel",), ("P1",), ("P3",), ("P6",), ("control_loss",)):
            with self.subTest(events=events):
                rig = Rig()
                permit = rig.human()
                rig.robot.bind(permit).forward()
                before = len(rig.output.outputs)

                def observe_read():
                    self.assertGreater(len(rig.output.outputs), before)
                    self.assertEqual(rig.output.outputs[-1][1], "zero")

                rig.reader.on_read = observe_read
                rig.robot.supervise(events=events)
                self.assertEqual(rig.robot.reservation.phase,
                                 "ended" if events[0] in {"stop", "cancel"} else "locked")
                self.assertFalse(rig.robot.valid_result(permit))

    def test_simultaneous_priorities_keep_all_causes_and_never_succeed(self):
        for events in permutations(("P6", "stop", "obstacle", "confirmation")):
            with self.subTest(events=events):
                rig = Rig()
                permit = rig.human()
                rig.clock.now = 5.0
                rig.reader.refresh()
                rig.facts = replace(rig.facts, input_audio_ready=False)
                rig.robot.supervise(events=events)
                self.assertEqual(rig.robot.reservation.phase, "locked")
                self.assertTrue(set(rig.robot.causes) >= {
                    *events, "deadline", "input_audio_ready",
                })
                self.assertFalse(rig.robot.valid_result(permit))
                self.assertFalse(rig.nonzero())

    def test_ordinary_deadline_stop_and_cancel_keep_faults(self):
        for events in ((), ("stop",), ("cancel",)):
            with self.subTest(events=events):
                rig = Rig()
                rig.human()
                rig.clock.now = 5.0
                rig.reader.refresh()
                rig.facts = replace(rig.facts, output_audio_ready=False)
                rig.robot.supervise(events=events)
                self.assertEqual(rig.robot.reservation.phase, "ended")
                self.assertIn("output_audio_ready", rig.robot.causes)
                self.assertIn("deadline", rig.robot.causes)
                self.assertEqual(rig.inhibition.requests, ["startup"])

    def test_stop_received_during_admission_callback_cannot_be_cleared_by_admission(self):
        rig = Rig()

        def stop_during_journal(event):
            if event["event"] == "admission_request":
                rig.robot.request_emergency_stop()

        rig.journal.on_write = stop_during_journal
        with self.assertRaisesRegex(ProtectionFault, "obsolete_request"):
            rig.human()
        self.assertIsNone(rig.robot.reservation)
        self.assertFalse(rig.nonzero())

    def test_refused_old_or_stationary_commands_do_not_poison_current_phase(self):
        for phase in ("holding", "acquiring", "active"):
            with self.subTest(phase=phase):
                rig = Rig(None)
                if phase == "acquiring":
                    permit = rig.robot.admit(
                        human=True, acquisition=True, conditions=lambda: rig.facts,
                    )
                    old = permit
                else:
                    old = rig.human()
                    if phase == "holding":
                        rig.robot.hold_human(old)
                        permit = old
                    else:
                        rig.robot.suspend("obstacle")
                        permit = rig.robot.resume()
                for command in ("forward", "backward", "left", "right", "set_speed"):
                    with self.assertRaises(ProtectionFault):
                        rig.robot.supervise(old, command, 0.1)
                self.assertEqual(rig.robot.reservation.permit, permit)
                self.assertEqual(rig.robot.reservation.phase, phase)
                self.assertFalse(rig.nonzero())

    def test_old_admission_request_stays_invalid_after_stop_is_cleared(self):
        rig = Rig()
        old = rig.robot.capture_admission_request()
        rig.robot.request_emergency_stop()
        rig.robot.clear_emergency_stop()
        with self.assertRaisesRegex(ProtectionFault, "obsolete_request"):
            rig.robot.admit(request=old)
        new = rig.robot.admit()
        self.assertTrue(rig.robot.valid_result(new))
        self.assertFalse(rig.nonzero())
        self.assertEqual(rig.inhibition.requests, ["startup"])

    def test_obstacle_at_admission_is_not_overridden_by_conditions(self):
        rig = Rig()
        rig.output.obstacle = True
        with self.assertRaisesRegex(ProtectionFault, "obstacle"):
            rig.human()
        self.assertFalse(rig.nonzero())
        self.assertIsNone(rig.robot.reservation)

    def test_motion_changes_during_journal_are_checked_again(self):
        for change, cause in (("speed", "human_speed"), ("obstacle", "obstacle")):
            with self.subTest(change=change):
                rig = Rig()
                permit = rig.human()

                def mutate(event):
                    if event["event"] == "command_requested":
                        if change == "speed":
                            rig.output.speed = 0.8
                        else:
                            rig.output.obstacle = True

                rig.journal.on_write = mutate
                with self.assertRaisesRegex(ProtectionFault, cause):
                    rig.robot.bind(permit).forward()
                self.assertFalse(rig.nonzero())

    def test_elapsed_rotation_request_is_not_emitted_after_a_slow_callback(self):
        rig = Rig()
        permit = rig.human()

        def delay(event):
            if event["event"] == "command_requested":
                rig.clock.now += 0.2
                rig.reader.refresh()

        rig.journal.on_write = delay
        with self.assertRaisesRegex(ProtectionFault, "motion_command_expired"):
            rig.robot.bind(permit).left_for(0.2)
        self.assertFalse(rig.nonzero())
        self.assertEqual(rig.output.outputs[-1][1], "zero")

    def test_p5_change_in_last_conditions_callback_cannot_authorize_output(self):
        rig = Rig()
        calls = 0

        def conditions():
            nonlocal calls
            calls += 1
            if calls == 3:
                rig.clock.now += 0.01
                rig.reader.sample = ProtectionState("inhibited", "off", 1.01, 1.01, ("P6",))
            return rig.facts

        permit = rig.robot.admit(human=True, deadline=5.0, conditions=conditions)
        with self.assertRaisesRegex(ProtectionFault, "armament_changed"):
            rig.robot.bind(permit).forward()
        self.assertFalse(rig.nonzero())
        self.assertEqual(rig.robot.reservation.phase, "locked")
        self.assertIn("P6", rig.robot.causes)

    def test_proof_failure_locks_and_journal_failure_does_not_renew_proof(self):
        for port in ("proof", "journal"):
            with self.subTest(port=port):
                rig = Rig()
                permit = rig.human()
                before = len(rig.proof.cycles)
                if port == "proof":
                    rig.proof.fail = True
                else:
                    def fail_journal(_):
                        raise OSError("journal failed")
                    rig.journal.on_write = fail_journal
                with self.assertRaises((OSError, ProtectionFault)):
                    rig.robot.bind(permit).forward()
                self.assertEqual(len(rig.proof.cycles), before)
                self.assertEqual(rig.output.outputs[-1][1], "zero")
                self.assertEqual(rig.robot.reservation.phase,
                                 "locked" if port == "proof" else "suspended")
                if port == "journal":
                    self.assertFalse(rig.nonzero())

    def test_protected_ball_initial_obstacle_never_emits_and_backward_is_preserved(self):
                    for command in ("forward_for", "left_for", "right_for", "backward_for"):
                        with self.subTest(command=command):
                            rig = Rig()
                            permit = rig.robot.admit()
                            rig.output.obstacle = True
                            outcome = getattr(rig.robot.bind(permit), command)(0.1)
                            if command == "backward_for":
                                self.assertIsNone(outcome)
                                self.assertEqual(rig.nonzero()[0][1], "backward")
                            else:
                                self.assertEqual(outcome, "obstacle")
                                self.assertFalse(rig.nonzero())
                            self.assertEqual(rig.output.outputs[-1][1], "zero")

    def test_protected_runtime_stop_is_terminal_and_not_a_mission_success(self):
                    with tempfile.TemporaryDirectory() as work:
                        rig = Rig()
                        runtime = VoiceRuntime(robot=rig.robot, use_llm=False, threaded=False, trace_dir=work)
                        result = runtime.handle_text_as_plan("stop")
                        self.assertEqual(result["status"], "stopped")
                        self.assertEqual(result["mission"]["phase"], "aborted")
                        self.assertEqual(len(result["steps"]), 1)
                        self.assertEqual(result["steps"][0]["attempt"], 1)
                        self.assertFalse(rig.nonzero())

    def test_direct_language_stop_invalidates_the_reserved_context(self):
        rig = Rig()
        permit = rig.human()
        result = LanguageController(robot=rig.robot).handle_intent(
            Intent(name="stop", raw_text="stop"),
        )
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(rig.robot.reservation.phase, "ended")
        self.assertFalse(rig.robot.valid_result(permit))
        self.assertFalse(rig.nonzero())

    def test_journal_fault_before_output_is_not_success_shaped(self):
        rig = Rig()
        permit = rig.human()

        def fail(event):
            if event["event"] == "command_requested":
                raise OSError("journal unavailable")

        rig.journal.on_write = fail
        with self.assertRaisesRegex(ProtectionFault, "journal_error"):
            rig.robot.bind(permit).forward()
        self.assertEqual(rig.robot.reservation.phase, "suspended")
        self.assertFalse(rig.nonzero())

    def test_conditions_and_deadline_revalidated_after_journal_latency(self):
        for fault in ("input_audio_ready", "deadline"):
            with self.subTest(fault=fault):
                rig = Rig()
                permit = rig.human()

                def change(event):
                    if event["event"] == "command_requested":
                        if fault == "deadline":
                            rig.clock.now = 5.0
                        else:
                            rig.facts = replace(rig.facts, input_audio_ready=False)
                        rig.reader.refresh()

                rig.journal.on_write = change
                with self.assertRaisesRegex(ProtectionFault, fault):
                    rig.robot.bind(permit).forward()
                self.assertFalse(rig.nonzero())

    def test_missing_or_malformed_p5_never_emits(self):
        for fields in (
            {"observed_at": "recent"}, {"transition_at": object()},
            {"causes": ["P6"]}, {"causes": (False,)},
        ):
            with self.subTest(fields=fields):
                rig = Rig()
                permit = rig.human()
                rig.reader.sample = replace(rig.reader.sample, **fields)
                with self.assertRaisesRegex(ProtectionFault, "p5_incoherent"):
                    rig.robot.bind(permit).forward()
                self.assertFalse(rig.nonzero())
                self.assertEqual(rig.robot.reservation.phase, "locked")

    def test_result_invalid_immediately_on_stop_and_deadline(self):
        for cause in ("stop", "deadline"):
            with self.subTest(cause=cause):
                rig = Rig()
                permit = rig.human()
                if cause == "stop":
                    rig.robot.request_emergency_stop()
                else:
                    rig.clock.now = 5.0
                self.assertFalse(rig.robot.valid_result(permit))

    def test_late_success_cannot_advance_runtime_or_restart_suspended_skill(self):
        for event, status in (("obstacle", "suspended"), ("P6", "aborted"), ("stop", "aborted")):
            with self.subTest(event=event), tempfile.TemporaryDirectory() as work:
                rig = Rig()
                permit = rig.human()
                runtime = VoiceRuntime(robot=rig.robot, use_llm=False, threaded=False, trace_dir=work)

                def late(context):
                    rig.robot.supervise(events=(event,))
                    return SkillResult(status="success", next_action="move_forward")

                skill = ScriptedSkill(late)
                result = runtime.execute_reserved_skill(permit, skill)
                self.assertEqual(result["status"], status)
                self.assertEqual(result["mission"], permit.mission)
                self.assertEqual(result["context"], permit.context)
                self.assertEqual(result["mission_deadline"], 5.0)
                self.assertEqual(result["required_action"],
                                 "correct_faults_then_explicit_resume" if event == "obstacle" else
                                 "manual_rearm_then_new_request" if event == "P6" else "new_request")
                self.assertEqual(skill.calls, 1)
                self.assertFalse(rig.nonzero())
                self.assertIsNone(runtime._reserved_context.state["last_skill_result"]
                                  if runtime._reserved_context is not None else None)

    def test_language_failure_stops_plan_and_exception_locks(self):
        for failure in ("failed", "exception"):
            with self.subTest(failure=failure):
                rig = Rig()
                controller = LanguageController(robot=rig.robot)

                def action(context):
                    if failure == "exception":
                        raise RuntimeError("unexpected skill failure")
                    return SkillResult(status="failed")

                first = ScriptedSkill(action)
                second = ScriptedSkill()
                controller.planner.plan = lambda _: [first, second]
                intent = Intent(name="move_forward", raw_text="avance")
                if failure == "exception":
                    with self.assertRaisesRegex(RuntimeError, "unexpected skill failure"):
                        controller.handle_intent(intent)
                    self.assertIn("language_exception", rig.robot.causes)
                    self.assertIn("language_exception", rig.inhibition.requests)
                else:
                    result = controller.handle_intent(intent)
                    self.assertEqual(result["status"], "aborted")
                    self.assertEqual(result["reason"], "skill_failed")
                self.assertEqual(second.calls, 0)
                self.assertFalse(rig.nonzero())
                self.assertEqual(rig.output.outputs[-1][1], "zero")

    def test_language_pending_preserves_ball_retry_contract_without_following_step(self):
        rig = Rig()
        controller = LanguageController(robot=rig.robot)
        first = ScriptedSkill(lambda _: SkillResult(status="in_progress"))
        second = ScriptedSkill()
        controller.planner.plan = lambda _: [first, second]
        result = controller.handle_intent(Intent(name="move_forward", raw_text="avance"))
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["results"][0].status, "in_progress")
        self.assertEqual(second.calls, 0)
        self.assertFalse(rig.nonzero())

    def test_expired_runtime_reservation_stops_without_executing_or_succeeding(self):
        with tempfile.TemporaryDirectory() as work:
            rig = Rig()
            permit = rig.human()
            runtime = VoiceRuntime(robot=rig.robot, use_llm=False, threaded=False, trace_dir=work)
            rig.robot.bind(permit).forward()
            rig.clock.now = 5.0
            rig.reader.refresh()
            skill = ScriptedSkill()
            result = runtime.execute_reserved_skill(permit, skill)
            self.assertEqual(result["status"], "aborted")
            self.assertIn("deadline", result["causes"])
            self.assertEqual(result["mission_deadline"], 5.0)
            self.assertEqual(result["required_action"], "new_request")
            self.assertEqual(skill.calls, 0)
            self.assertIsNone(rig.robot.reservation)
            self.assertEqual(rig.output.outputs[-1][1], "zero")

    def test_stationary_human_terminal_receipt_retains_identity_deadline_and_all_faults(self):
        for event, action in (("P6", "manual_rearm_then_new_request"),
                              ("stop", "new_request"), ("deadline", "new_request"),
                              ("obstacle", "correct_faults_then_explicit_resume")):
            with self.subTest(event=event), tempfile.TemporaryDirectory() as work:
                rig = Rig()
                runtime = VoiceRuntime(robot=rig.robot, use_llm=False, threaded=False, trace_dir=work)
                identity = MarkerIdentity("synthetic", "synthetic", "1")
                runtime.settings = RuntimeSettings(human_marker_identity=identity)
                runtime.prepare_human_follow(
                    HumanFollowRequest(), conditions=lambda: rig.facts, journal=rig.journal,
                )
                context = runtime.human_follow_snapshot.context
                for number in range(1, 4):
                    rig.clock.now += 0.01
                    rig.reader.refresh()
                    runtime.advance_human_follow(observation=MarkerObservation(
                        "synthetic-source", "synthetic-stream", number,
                        rig.clock.now, rig.clock.now, context.mission_id, context.context_version,
                        ObservationDisposition.VALID, identity, 640, 480, 320.0, 240.0, 0.0,
                        160.0, 150.0, "synthetic-calibration", MarkerQuality(True, True),
                    ))
                active = runtime.advance_human_follow(
                    completed_announcement=runtime.pending_human_announcement.token,
                )
                deadline = active["mission_deadline"]
                if event == "deadline":
                    rig.clock.now = deadline
                    rig.reader.refresh()
                rig.facts = replace(rig.facts, input_audio_ready=False)
                result = runtime.advance_human_follow(events=(event,))
                self.assertEqual(result["mission"], context.mission_id)
                self.assertEqual(result["context"], context.context_version)
                self.assertEqual(result["mission_deadline"], deadline)
                self.assertEqual(result["required_action"], action)
                self.assertIn("input_audio_ready", result["causes"])
                self.assertIn(event, result["causes"])
                self.assertFalse(rig.nonzero())
                if event != "obstacle":
                    self.assertIsNone(runtime.human_follow_snapshot)
                    self.assertIn(result["outcome"], {"locked", "stop", "deadline"})

    def test_direct_human_cycle_exception_stops_locks_and_invalidates(self):
        rig = Rig()
        session = HumanFollowRuntime(
            rig.robot, RuntimeSettings(human_marker_identity=MarkerIdentity("synthetic", "dict", "1")),
            HumanFollowRequest(), lambda: rig.facts, rig.journal,
        )
        with self.assertRaises(TypeError):
            session.cycle(frame=object(), provider=object())
        self.assertIsNone(session.snapshot.context)
        self.assertFalse(rig.nonzero())
        self.assertIn("human_cycle_exception", rig.robot.causes)
        self.assertEqual(session.result_metadata()["required_action"], "manual_rearm_then_new_request")

    def test_observer_failure_is_not_proof_of_no_output(self):
        rig = Rig()
        permit = rig.human()
        before = len(rig.proof.cycles)
        rig.output.fail_stop = True
        with self.assertRaises(Exception):
            rig.robot.supervise(events=("stop",))
        self.assertEqual(len(rig.proof.cycles), before)
        self.assertTrue(rig.inhibition.requests[-1].startswith("cycle_exception"))
        rig.output.fail_stop = False
        rig.robot.finish(permit)
