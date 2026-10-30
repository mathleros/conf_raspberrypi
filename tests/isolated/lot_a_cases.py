"""Explicitly loaded lot A oracles; all numbers below are FICTIONAL."""

from dataclasses import replace
import json
from itertools import permutations, product
from types import SimpleNamespace

import inspect
from pathlib import Path
import tempfile
import threading
import unittest
import sys
from unittest.mock import patch

from irobot.domain.skills.base_skill import Skill, SkillContext, SkillResult
from irobot.domain.orchestrator.executor import SkillExecutor
from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.domain.skills.behaviors.follow_object import FollowObjectSkill
from irobot.config.settings import RuntimeSettings
from irobot.interfaces.intent_parser import Intent, IntentParser
from irobot.interfaces.language_controller import LanguageController
from irobot.interfaces.plan_guards import requests_human_follow
from irobot.interfaces.protection import (
    HumanConditions, MissionPermit, ProtectionFault, ProtectionPorts, ProtectionState,
)
from irobot.interfaces.robot_controller import RobotController
from irobot.interfaces.voice_runtime import VoiceRuntime
from irobot.interfaces import voice_runtime as vr
from tests.unit.fake_robot import FakeRobot


REQUIRED_HUMAN_CONDITIONS = (
    "request_valid", "configuration_qualified", "terrain_checked",
    "safe_access_demonstrated", "protections_qualified", "camera_context_valid",
    "marker_acquired", "identity_valid", "observations_fresh", "distance_valid",
    "obstacle_clear", "swept_volume_protected", "input_audio_ready",
    "output_audio_ready", "journal_ready", "movement_allowed", "limits_valid",
)


def cases(names, values):
    """Explicit stdlib test matrix, unrelated to the unavailable pytest suite."""
    def decorate(function):
        axes = getattr(function, "axes", [])
        function.axes = [*axes, (names.replace(" ", "").split(","), values)]
        return function
    return decorate


def expect_error(error, match=""):
    return unittest.TestCase().assertRaisesRegex(error, match)


def unexpected_llm(*_):
    raise AssertionError("LLM called")


class Clock:
    def __init__(self):
        self.now = 0.0
        self.on_wait = lambda: None

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        self.on_wait()


class P5:
    def __init__(self, clock):
        self.clock = clock
        self.sample = ProtectionState("inhibited", "boot", 0.0, 0.0, ("startup",))
        self.error = False

    def read(self):
        if self.error:
            raise OSError("scripted P5 failure")
        return self.sample

    def refresh(self):
        if self.sample is not None:
            self.sample = replace(self.sample, observed_at=self.clock.time())

    def transition(self, state, token, *causes):
        self.sample = ProtectionState(
            state, token, self.clock.time(), self.clock.time(), tuple(causes),
        )


class Witness:
    def __init__(self):
        self.events = []
        self.cycles = []
        self.requests = []
        self.journal = []
        self.fail_proof = False
        self.fail_request = False
        self.fail_journal = False

    def emit(self, cycle):
        if self.fail_proof:
            raise OSError("scripted proof port")
        self.events.append(("proof", cycle))
        self.cycles.append(cycle)

    def request(self, cause):
        if self.fail_request:
            raise OSError("scripted inhibition port")
        self.requests.append(cause)
        self.events.append(("inhibition_requested", cause))

    def write(self, event):
        if self.fail_journal:
            raise OSError("scripted journal port")
        self.journal.append(event)
        self.events.append(("journal", event["event"]))


class Motor(FakeRobot):
    def __init__(self, witness):
        super().__init__()
        self.witness = witness
        self.fail_motion = False
        self.fail_stop = False

    def _record(self, command):
        if self.fail_motion and command != "stop":
            raise OSError("scripted output failure")
        if self.fail_stop and command == "stop":
            raise OSError("scripted zero output failure")
        super()._record(command)
        self.witness.events.append(("motor", command))

    def set_speed(self, speed):
        self._record(("speed", speed))
        self.speed = speed

    def stop(self):
        self.witness.events.append(("zero_attempted", None))
        super().stop()


class Rig:
    def __init__(self, present=True):
        self.clock = Clock()
        self.p5 = P5(self.clock)
        self.witness = Witness()
        self.motor = Motor(self.witness)
        self.facts = HumanConditions(**{key: True for key in REQUIRED_HUMAN_CONDITIONS})
        self.condition_hook = None
        ports = ProtectionPorts(self.p5, self.witness, self.witness, 0.25, self.witness)
        self.robot = RobotController(
            self.motor, self.clock.time, self.clock.sleep,
            protection="present" if present else "absent", ports=ports if present else None,
        )
        self.clock.on_wait = self.p5.refresh
        if present:
            self.robot.supervise()
            self.clock.now = 1.0
            self.p5.transition("armed", "arm-A")
            self.robot.supervise()

    def conditions(self):
        self.witness.events.append(("conditions", "evaluated"))
        if self.condition_hook is not None:
            return self.condition_hook()
        return self.facts

    def human(self):
        return self.robot.admit(human=True, deadline=7.0, conditions=self.conditions)

    def runtime(self, path):
        return VoiceRuntime(robot=self.robot, use_llm=False, threaded=False, trace_dir=str(path))


def nonzero(motor):
    # Independent output observer, not the tested journal.
    assert motor is not None, "observer unavailable: inconclusive"
    return [c for c in motor.commands if c != "stop"]


@cases("condition", REQUIRED_HUMAN_CONDITIONS)
def test_o1_each_human_condition(condition):
    rig = Rig()
    permit = rig.human()
    rig.facts = replace(rig.facts, **{condition: False})
    with expect_error(ProtectionFault, match=condition):
        rig.robot.bind(permit).forward()
    assert not nonzero(rig.motor)
    assert rig.robot.reservation.phase == "suspended"
    rig.robot.bind(permit).stop()


def test_o1_nominal_deadline_and_no_mission():
    rig = Rig()
    with expect_error(ProtectionFault, match="no_mission"):
        rig.robot.forward()
    permit = rig.human()
    rig.robot.bind(permit).forward()
    assert nonzero(rig.motor) == ["forward"]
    rig.clock.now = 7.0
    rig.p5.refresh()
    with expect_error(ProtectionFault, match="deadline"):
        rig.robot.bind(permit).right()
    assert nonzero(rig.motor) == ["forward"]
    assert rig.robot.reservation.phase == "ended"


def test_o1_human_requires_explicit_bounded_deadline():
    rig = Rig()
    with expect_error(ProtectionFault, match="deadline_required"):
        rig.robot.admit(human=True, conditions=rig.conditions)
    assert rig.robot.reservation is None and not nonzero(rig.motor)


@cases("sample,reason", [
    (None, "p5_absent"),
    (ProtectionState("unknown", "x", 1, 1), "p5_unknown"),
    (ProtectionState("armed", "", 1, 1), "p5_incoherent"),
    (ProtectionState("armed", "x", 2, 1), "p5_incoherent"),
    (ProtectionState("armed", "x", 1, 2), "p5_incoherent"),
    (ProtectionState("armed", "x", float("nan"), 1), "p5_incoherent"),
    (ProtectionState("inhibited", "off", 1.1, 1.1, ("P6",)), "P6"),
])
def test_o2_invalid_p5(sample, reason):
    rig = Rig()
    permit = rig.human()
    if sample is not None and sample.state == "inhibited":
        rig.clock.now = 1.1
    rig.p5.sample = sample
    with expect_error(ProtectionFault, match=reason):
        rig.robot.bind(permit).forward()
    assert not nonzero(rig.motor)
    assert rig.robot.reservation.phase == "locked"


@cases("age,allowed", [(0.249, True), (0.25, True), (0.251, False)])
def test_o2_fictional_age_boundary_no_refresh_by_read(age, allowed):
    rig = Rig()
    permit = rig.human()
    original = rig.p5.sample
    rig.clock.now += age
    if allowed:
        rig.robot.bind(permit).forward()
        assert nonzero(rig.motor) == ["forward"]
    else:
        with expect_error(ProtectionFault, match="p5_stale"):
            rig.robot.bind(permit).forward()
        assert not nonzero(rig.motor)
    assert rig.p5.sample is original


def test_o2_reader_error_is_not_absence_fallback():
    rig = Rig()
    permit = rig.human()
    rig.p5.error = True
    with expect_error(ProtectionFault, match="p5_read_error"):
        rig.robot.bind(permit).forward()
    assert not nonzero(rig.motor)


@cases("field", ["mission", "context", "armament", "generation"])
def test_o3_obsolete_ids_and_zero(field):
    rig = Rig()
    permit = rig.human()
    obsolete = replace(permit, **{field: "old" if field in {"armament", "generation"} else -1})
    with expect_error(ProtectionFault, match="obsolete_context"):
        rig.robot.bind(obsolete).set_speed(0.7)
    rig.robot.bind(obsolete).set_speed(0)
    assert not nonzero(rig.motor)
    assert rig.motor.commands[-1] == "stop"


def test_o3_no_public_delegation_or_internal_temporized_bypass():
    rig = Rig()
    permit = rig.human()
    for surface in (rig.robot, rig.robot.bind(permit)):
        for attribute in ("robot", "pins", "ena", "distance_sensor", "arbitrary_motion"):
            with expect_error(AttributeError):
                getattr(surface, attribute)
    with expect_error(ProtectionFault, match="obsolete_context"):
        rig.robot._run_motion_for(rig.motor.forward, 0.1)
    with expect_error(ProtectionFault, match="internal_entry_forbidden"):
        rig.robot._dispatch("forward")
    assert not nonzero(rig.motor)
    old = rig.robot.bind(permit)
    rig.robot.suspend("obstacle")
    new = rig.robot.resume()
    assert new.mission == permit.mission and new.context != permit.context
    with expect_error(ProtectionFault, match="obsolete_context"):
        old.left()
    rig.robot.bind(new).forward()
    assert nonzero(rig.motor) == ["forward"]


def test_o4_complete_order_idle_and_partial_cycle():
    rig = Rig()
    initial = len(rig.witness.cycles)
    rig.robot.supervise()
    assert len(rig.witness.cycles) == initial + 1
    permit = rig.human()
    rig.witness.events.clear()
    rig.robot.bind(permit).forward()
    assert rig.witness.events.index(("conditions", "evaluated")) < rig.witness.events.index(("motor", "forward"))
    assert rig.witness.events[-1][0] == "proof"
    assert rig.witness.cycles == sorted(set(rig.witness.cycles))
    count = len(rig.witness.cycles)

    def incomplete():
        raise RuntimeError("scripted blocked/partial evaluation")

    rig.condition_hook = incomplete
    with expect_error(RuntimeError, match="partial"):
        rig.robot.supervise()
    assert len(rig.witness.cycles) == count
    assert rig.motor.commands[-1] == "stop"
    assert rig.robot.reservation.phase == "locked"


@cases("condition", REQUIRED_HUMAN_CONDITIONS)
def test_o1_admission_conditions_independently(condition):
    rig = Rig()
    rig.facts = replace(rig.facts, **{condition: False})
    with expect_error(ProtectionFault, match=condition):
        rig.human()
    assert rig.robot.reservation is None and not nonzero(rig.motor)


def test_o3_p5_changes_during_preconditions_before_output():
    rig = Rig()
    permit = rig.human()

    def conditions():
        rig.clock.now += 0.01
        rig.p5.transition("inhibited", "changed-during-check", "P1")
        return rig.facts

    rig.condition_hook = conditions
    with expect_error(ProtectionFault, match="armament_changed"):
        rig.robot.bind(permit).forward()
    assert not nonzero(rig.motor)
    assert rig.robot.reservation.phase == "locked"


@cases("event", ["stop", "obstacle", "perception", "audio"])
def test_o5_ordinary_does_not_request_inhibition(event):
    rig = Rig()
    rig.human()
    rig.robot.supervise(events=(event,))
    assert rig.witness.requests == ["startup"]
    assert rig.motor.commands[-1] == "stop"


@cases("cause", ["P1", "P3", "P6", "unknown"])
@cases("order", list(permutations(("stop", "deadline", "confirmation"))))
def test_o6_p1_wins_and_keeps_all_causes(cause, order):
    rig = Rig()
    permit = rig.human()
    rig.clock.now = 7.0
    rig.p5.transition("inhibited", "off", cause)
    rig.robot.supervise(events=order)
    assert rig.robot.reservation.phase == "locked"
    assert set(rig.robot.causes) >= {cause, *order}
    assert rig.witness.requests[0] == "startup"
    assert cause in rig.witness.requests[-1]
    with expect_error(ProtectionFault):
        rig.robot.bind(permit).forward()
    with expect_error(ProtectionFault):
        rig.robot.resume()
    assert not nonzero(rig.motor)


def test_o7_rearm_posteriority_and_quick_restart():
    rig = Rig()
    permit = rig.human()
    old_sample = rig.p5.sample
    rig.clock.now = 2.0
    rig.robot.priority_one("P1")
    rig.robot.clear_emergency_stop()
    rig.robot.finish(permit)
    rig.p5.sample = replace(old_sample, armament="merely-different")
    with expect_error(ProtectionFault):
        rig.robot.admit()
    rig.p5.sample = old_sample
    with expect_error(ProtectionFault):
        rig.robot.admit()
    rig.clock.now = 3.0
    rig.p5.transition("inhibited", "off", "P1")
    rig.robot.supervise()
    rig.clock.now = 4.0
    rig.p5.transition("armed", "arm-B")
    rig.robot.supervise()
    assert not nonzero(rig.motor) and rig.robot.reservation is None
    new = rig.robot.admit()
    rig.robot.bind(new).right()
    assert nonzero(rig.motor) == ["right"]
    restarted = RobotController(
        rig.motor, rig.clock.time, rig.clock.sleep, protection="present",
        ports=ProtectionPorts(rig.p5, rig.witness, rig.witness, 0.25),
    )
    with expect_error(ProtectionFault, match="rearm_required"):
        restarted.admit()
    assert rig.witness.requests[-1] == "startup"


def test_o7_request_must_follow_rearm_observation_not_trigger_its_admission():
    rig = Rig()
    rig.robot.priority_one("P1")
    rig.clock.now = 2.0
    rig.p5.transition("inhibited", "after-event", "P1")
    rig.robot.supervise()
    rig.clock.now = 3.0
    rig.p5.transition("armed", "after-rearm")
    with expect_error(ProtectionFault, match="rearm_required"):
        rig.robot.admit()
    assert rig.robot.reservation is None and not nonzero(rig.motor)
    permit = rig.human()
    rig.robot.bind(permit).forward()
    assert nonzero(rig.motor) == ["forward"]


class SyntheticSkill(Skill):
    name = "synthetic_human_only"

    def __init__(self, rig, suspend=False, p1=False):
        self.rig = rig
        self.suspend = suspend
        self.p1 = p1
        self.calls = 0
        self.contexts = []
        self.context_counts = []

    def execute(self, context):
        self.calls += 1
        self.contexts.append(id(context))
        context.state["synthetic_count"] = context.state.get("synthetic_count", 0) + 1
        self.context_counts.append(context.state["synthetic_count"])
        context.robot.forward()
        if self.suspend:
            self.suspend = False
            self.rig.robot.suspend("perception")
        if self.p1:
            self.rig.robot.priority_one("P6")
        return SkillResult(status="success")


def test_o8_reservation_worker_done_resume_deadline_stop_local(tmp_path):
    rig = Rig()
    runtime = rig.runtime(tmp_path)
    permit = rig.human()
    skill = SyntheticSkill(rig, suspend=True)
    results = []
    runtime._worker = threading.Thread(
        target=lambda: results.append(runtime.execute_reserved_skill(permit, skill)),
        name="isolated-synthetic-worker",
    )
    with patch.object(vr, "ask_llm_for_intent_plan_with_trace", unexpected_llm):
        runtime._worker.start()
        runtime._worker.join(2)
        assert not runtime._worker.is_alive(), "synthetic worker did not finish"
        assert results[0]["status"] == "suspended"
    assert runtime.mission_running()
    deadline = rig.robot.reservation.deadline
    assert runtime.handle_text_as_plan("recule")["reason"] == "mission_reserved"
    assert skill.calls == 1
    assert runtime.handle_text_as_plan("reprends le suivi")["status"] == "success"
    assert deadline == 7.0 and rig.robot.reservation is None
    assert skill.calls == 2
    assert skill.contexts[0] == skill.contexts[1]
    assert skill.context_counts == [1, 2]
    assert runtime._reserved_context is None
    assert runtime.handle_text_as_plan("reprends le suivi")["reason"] == "no_resumable_session"
    rig.human()
    runtime.handle_transcript("stop")
    assert not runtime.mission_running()
    assert rig.witness.requests == ["startup"]


def test_o8_suspended_deadline_not_reset_and_no_automatic_resume(tmp_path):
    rig = Rig()
    runtime = rig.runtime(tmp_path)
    permit = rig.human()
    skill = SyntheticSkill(rig, suspend=True)
    assert runtime.execute_reserved_skill(permit, skill)["status"] == "suspended"
    rig.clock.now = 6.99
    rig.p5.refresh()
    runtime.supervise_once()
    assert skill.calls == 1
    assert rig.robot.reservation.deadline == 7.0
    rig.clock.now = 7.0
    rig.p5.refresh()
    assert "deadline" in runtime.handle_text_as_plan("reprends le suivi")["reason"]
    assert rig.robot.reservation is None
    assert skill.calls == 1
    assert nonzero(rig.motor) == ["forward"]


def test_o6_late_synthetic_success_never_substitutes_for_p1(tmp_path):
    rig = Rig()
    runtime = rig.runtime(tmp_path)
    skill = SyntheticSkill(rig, p1=True)
    result = runtime.execute_reserved_skill(rig.human(), skill)
    assert result["status"] == "aborted"
    assert result["reason"] == "protection_fault"
    assert skill.calls == 1 and rig.robot.reservation is None
    assert nonzero(rig.motor) == ["forward"]
    assert rig.motor.commands[-1] == "stop"


def test_o3_executor_discards_previous_result_and_never_runs_stale_step():
    rig = Rig()
    permit = rig.human()
    context = SkillContext(robot=rig.robot.bind(permit))
    context.state["last_skill_result"] = SkillResult(status="success")
    rig.robot.priority_one("P1")
    skill = SyntheticSkill(rig)
    result = SkillExecutor(context).run(skill)
    assert result.status == "failed" and result.data["protection_fault"]
    assert context.state["last_skill_result"] is None
    assert skill.calls == 0 and not nonzero(rig.motor)


@cases("text", [
    "suis-moi", "follow me", "suis une personne", "suis nous",
    "avance puis suis-moi", "suis-moi puis cherche la balle jaune",
    "cherche la balle puis suis moi pendant 20 secondes",
    "suis ma femme", "suis mon mari", "suis mes enfants", "follow my wife",
    "avance puis suis ma femme", "suis notre ami", "suivez votre opérateur",
    "suis une autre personne", "suis ma jeune femme", "suis l'autre opérateur",
])
def test_o9_real_human_refusal_all_entries(text, tmp_path):
    rig = Rig(present=False)
    registry = SkillRegistry.default()
    registry.register(FollowObjectSkill(
        settings=RuntimeSettings(), time_fn=rig.clock.time, sleep_fn=rig.clock.sleep,
    ))
    runtime = VoiceRuntime(
        robot=rig.robot, registry=registry, use_llm=False,
        threaded=False, trace_dir=str(tmp_path),
    )
    with patch.object(vr, "ask_llm_for_intent_plan_with_trace", unexpected_llm):
        for entry in (runtime.handle_text, runtime.handle_text_as_plan, runtime.handle_transcript):
            assert entry(text)["reason"] == "human_capability_unavailable"
    assert IntentParser().parse(text).name == "follow_person"
    assert LanguageController(robot=rig.robot, registry=registry).handle_text(text)["status"] == "rejected"
    assert not nonzero(rig.motor)


def test_o9_llm_human_plan_rejected_in_full(tmp_path):
    rig = Rig(False)
    runtime = rig.runtime(tmp_path)
    runtime.use_llm = True
    with patch.object(vr, "ask_llm_for_intent_plan_with_trace", lambda *_: (
        [Intent("move_forward"), Intent("follow_person")], {"source": "fixture"})):
        result = runtime.handle_text_as_plan("commande opaque")
    assert result["status"] == "rejected" and result["steps"] == []
    assert not nonzero(rig.motor)
    assert runtime.controller.handle_intent(Intent("follow_person"))["reason"] == "human_capability_unavailable"


@cases("human_step", [
    {"intent": "follow_person", "parameters": []},
    {"intent": "execute_path", "parameters": {"path": [{"action": "follow_person"}]}},
])
def test_o9_raw_llm_cannot_hide_human_in_malformed_or_nested_step(human_step, tmp_path):
    rig = Rig(False)
    runtime = rig.runtime(tmp_path)
    runtime.use_llm = True
    content = json.dumps({"steps": [{"intent": "move_forward"}, human_step]})
    with patch.object(vr, "_post_llm_chat", return_value=content):
        result = runtime.handle_text_as_plan("avance")
    assert result["status"] == "rejected"
    assert result["reason"] == "human_capability_unavailable"
    assert not nonzero(rig.motor)
    for file in tmp_path.glob("*.jsonl"):
        assert "follow_person" not in file.read_text()


@cases("present", [False, True])
def test_o10_same_runtime_ball_human_ball_and_primitives(present, tmp_path):
    rig = Rig(present)
    registry = SkillRegistry.default()
    registry.register(FollowObjectSkill(
        settings=RuntimeSettings(), time_fn=rig.clock.time, sleep_fn=rig.clock.sleep,
    ))
    perception = SimpleNamespace(detect=lambda **_: SimpleNamespace(
        position="center", distance_cm=180, label="yellow", confidence=1.0,
    ))
    runtime = VoiceRuntime(
        robot=rig.robot, perception=perception, registry=registry,
        use_llm=False, threaded=False, trace_dir=str(tmp_path),
    )
    for index in range(2):
        before = len(nonzero(rig.motor))
        result = runtime.handle_text_as_plan("suis la balle jaune pendant 1 seconde")
        assert result["status"] == "accepted"
        assert "forward" in nonzero(rig.motor)[before:]
        if index == 0:
            if present:
                permit = rig.human()
                assert runtime.execute_reserved_skill(permit, SyntheticSkill(rig))["status"] == "success"
            else:
                assert runtime.handle_text("suis-moi")["status"] == "rejected"
    for phrase, command in (("recule pendant 1 seconde", "backward"),
                            ("tourne à gauche pendant 1 seconde", "left"),
                            ("tourne à droite pendant 1 seconde", "right")):
        before = len(nonzero(rig.motor))
        result = runtime.handle_text_as_plan(phrase)
        assert result["status"] == "accepted"
        assert command in nonzero(rig.motor)[before:]
    assert runtime.handle_text_as_plan("stop")["status"] == "accepted"
    assert rig.robot.reservation is None
    assert rig.motor.commands[-1] == "stop"


def test_o10_p5_loss_no_retry_no_next_step_or_speed_restore(tmp_path):
    rig = Rig()
    runtime = rig.runtime(tmp_path)

    def lose():
        rig.p5.transition("inhibited", "off", "P3")

    rig.clock.on_wait = lose
    result = runtime.handle_text_as_plan("tourne à droite pendant 1 seconde puis avance")
    assert result["status"] == "aborted"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["attempt"] == 1
    assert nonzero(rig.motor) == [("speed", 0.5), "right"]
    assert rig.motor.commands[-1] == "stop"


@cases("position,distance,expected", [
    ("center", 40, "backward"), ("left", 100, "left"),
    ("right", 100, "right"), (None, None, "right"),
])
def test_o10_protected_ball_has_no_human_restrictions(position, distance, expected, tmp_path):
    rig = Rig()
    rig.facts = HumanConditions()
    registry = SkillRegistry.default()
    registry.register(FollowObjectSkill(
        settings=RuntimeSettings(), time_fn=rig.clock.time, sleep_fn=rig.clock.sleep,
    ))
    perception = SimpleNamespace(detect=lambda **_: None if position is None else SimpleNamespace(
        position=position, distance_cm=distance, label="yellow", confidence=1.0,
    ))
    runtime = VoiceRuntime(
        robot=rig.robot, perception=perception, registry=registry,
        use_llm=False, threaded=False, trace_dir=str(tmp_path),
    )
    if position is None:
        waiting = runtime.handle_text_as_plan("suis la balle jaune pendant 3 secondes")
        assert waiting["status"] == "accepted"
        assert not nonzero(rig.motor)
    result = runtime.handle_text_as_plan("suis la balle jaune pendant 4 secondes")
    assert result["status"] == "accepted"
    assert expected in nonzero(rig.motor)
    assert rig.motor.commands[-1] == "stop"
    assert rig.witness.requests == ["startup"]


def test_o3_deadline_crossed_during_evaluation():
    rig = Rig()
    permit = rig.human()

    def conditions():
        rig.clock.now = 7.0
        rig.p5.refresh()
        return rig.facts

    rig.condition_hook = conditions
    with expect_error(ProtectionFault, match="deadline"):
        rig.robot.bind(permit).forward()
    assert not nonzero(rig.motor)


def test_o9_live_protected_assembly_refused_before_any_import():
    with patch.object(vr, "load_runtime_settings", return_value=RuntimeSettings(protection_presence="present")):
        with expect_error(RuntimeError, match="no qualified real P5 adapter"):
            vr.build_hardware_runtime()


@cases("port", ["proof", "request", "journal"])
def test_o11_port_failure_visible_stop_not_success(port):
    rig = Rig()
    permit = rig.human()
    setattr(rig.witness, "fail_" + port, True)
    with expect_error((OSError, ProtectionFault)):
        if port == "request":
            rig.robot.priority_one("P1")
        else:
            rig.robot.bind(permit).forward()
    assert rig.motor.commands[-1] == "stop"
    assert rig.robot.reservation.phase != "active"
    if port == "journal":
        assert rig.robot.reservation.phase == "suspended"
        assert rig.witness.requests == ["startup"]
    assert not any("physical" in str(event) for event in rig.witness.journal)


def test_o11_zero_failure_not_confirmed_proof_not_emitted():
    rig = Rig()
    permit = rig.human()
    count = len(rig.witness.cycles)
    rig.motor.fail_stop = True
    with expect_error(OSError):
        rig.robot.priority_one("P1")
    assert len(rig.witness.cycles) == count
    assert rig.robot.reservation.phase == "locked"
    rig.motor.fail_stop = False
    rig.robot.bind(permit).stop()


def replay(script):
    rig = Rig()
    permit = rig.human()
    statuses = []
    for action in script:
        if action == "suspend":
            rig.robot.suspend("audio")
        elif action == "P6":
            rig.robot.priority_one("P6")
        else:
            try:
                rig.robot.bind(permit).forward()
                statuses.append("emitted")
            except ProtectionFault:
                statuses.append("refused")
    return statuses, nonzero(rig.motor), rig.robot.reservation.phase


def test_o12_replay_recalculates_decisions_with_fixed_expected():
    script = ("forward", "suspend", "forward", "P6", "forward")
    expected = (["emitted", "refused", "refused"], ["forward"], "locked")
    assert replay(script) == expected
    assert replay(script) == expected
    assert replay(("suspend", "forward")) == (["refused"], [], "suspended")


def test_configuration_errors_are_not_absence():
    with expect_error(ValueError):
        RobotController(FakeRobot(), protection="invalid")
    with expect_error(ValueError, match="ports"):
        RobotController(FakeRobot(), protection="present")
    with expect_error(ValueError):
        ProtectionPorts(None, None, None, 1)
    rig = Rig()
    with expect_error(AttributeError):
        rig.robot.protection_present = False


def test_o3_admission_and_resume_do_not_overwrite_new_p1():
    rig = Rig()

    def interrupt():
        rig.robot.priority_one("P1")
        return rig.facts

    rig.condition_hook = interrupt
    with expect_error(ProtectionFault, match="rearm_required"):
        rig.human()
    assert rig.robot.reservation is None and not nonzero(rig.motor)
    rig = Rig()
    permit = rig.human()
    rig.robot.suspend("audio")

    def interrupt_resume():
        rig.robot.priority_one("P6")
        return rig.facts

    rig.condition_hook = interrupt_resume
    with expect_error(ProtectionFault):
        rig.robot.resume()
    assert not rig.robot.valid_result(permit)
    assert rig.robot.reservation.phase == "locked"
    snapshot = rig.robot.reservation
    snapshot.phase = "active"
    assert rig.robot.reservation.phase == "locked"


def test_o5_idle_physical_cause_requests_once():
    rig = Rig()
    rig.clock.now += 0.01
    rig.p5.transition("inhibited", "P6-idle", "P6")
    rig.robot.supervise()
    rig.robot.supervise()
    assert rig.witness.requests == ["startup", "P6"]
    assert not nonzero(rig.motor)


def test_o12_observer_absent_is_not_a_pass():
    with expect_error(AssertionError, match="inconclusive"):
        nonzero(None)


def test_o4_monitored_idle_loop_no_independent_proof(tmp_path):
    rig = Rig()
    runtime = rig.runtime(tmp_path)
    remaining = 3
    before = len(rig.witness.cycles)

    def read():
        nonlocal remaining
        remaining -= 1
        return None

    runtime.run_supervised(read, lambda: remaining > 0)
    assert len(rig.witness.cycles) == before + 3
    assert not nonzero(rig.motor)
    before = len(rig.witness.cycles)

    def blocked():
        raise RuntimeError("scripted incomplete request cycle")

    with expect_error(RuntimeError, match="incomplete"):
        runtime.run_supervised(blocked, lambda: True)
    assert len(rig.witness.cycles) == before
    assert rig.witness.requests[-1] == "supervised_loop_exception"


def test_o12_runtime_replay_recalculates_reservation_and_cleanup(tmp_path):
    def replay_runtime(path):
        rig = Rig()
        runtime = rig.runtime(path)
        states = [runtime.handle_text_as_plan("avance pendant 1 seconde")["status"]]
        permit = rig.human()
        states.append(runtime.execute_reserved_skill(permit, SyntheticSkill(rig, suspend=True))["status"])
        states.append(runtime.handle_text_as_plan("recule pendant 1 seconde")["status"])
        states.append(runtime.handle_text_as_plan("reprends le suivi")["status"])
        states.append(runtime.handle_text_as_plan("recule pendant 1 seconde")["status"])
        return states, nonzero(rig.motor), rig.robot.reservation

    expected = (["accepted", "suspended", "rejected", "success", "accepted"],
                ["forward", "forward", "forward", "backward"], None)
    assert replay_runtime(tmp_path / "first") == expected
    assert replay_runtime(tmp_path / "second") == expected


@cases("event", ["P1", "stop"])
def test_o6_concurrent_interrupt_during_incomplete_evaluation(event):
    rig = Rig()
    permit = rig.human()
    entered = threading.Event()
    release = threading.Event()
    stopped = threading.Event()
    errors = []
    original_stop = rig.motor.stop

    def observe_stop():
        original_stop()
        stopped.set()

    def conditions():
        entered.set()
        if not release.wait(2):
            raise AssertionError("controlled wait timed out")
        return rig.facts

    rig.motor.stop = observe_stop
    rig.condition_hook = conditions

    def motion():
        try:
            rig.robot.bind(permit).forward()
        except ProtectionFault as exc:
            errors.append(str(exc))

    action = rig.robot.request_emergency_stop if event == "stop" else lambda: rig.robot.priority_one("P1")
    worker = threading.Thread(target=motion, name="isolated-evaluation")
    interrupt = threading.Thread(target=action, name="isolated-interrupt")
    proof_count = len(rig.witness.cycles)
    worker.start()
    try:
        assert entered.wait(2), "evaluation observer unavailable"
        interrupt.start()
        assert stopped.wait(2), "zero output not observed while evaluation incomplete"
        assert len(rig.witness.cycles) == proof_count
        assert not nonzero(rig.motor)
    finally:
        release.set()
        worker.join(2)
        if interrupt.ident is not None:
            interrupt.join(2)
    assert not worker.is_alive() and not interrupt.is_alive()
    assert errors and not nonzero(rig.motor)
    assert rig.robot.reservation.phase == ("locked" if event == "P1" else "ended")


def test_o4_listener_cannot_renew_for_blocked_worker(tmp_path):
    rig = Rig()
    runtime = rig.runtime(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    results = []

    class BlockedSkill(Skill):
        def execute(self, context):
            entered.set()
            if not release.wait(2):
                raise AssertionError("controlled worker wait timed out")
            return SkillResult(status="success")

    permit = rig.human()
    runtime._worker = threading.Thread(
        target=lambda: results.append(runtime.execute_reserved_skill(permit, BlockedSkill())),
        name="isolated-blocked-worker",
    )
    runtime._worker.start()
    try:
        assert entered.wait(2), "worker observer unavailable"
        count = len(rig.witness.cycles)
        runtime.handle_transcript("recule")
        assert len(rig.witness.cycles) == count
        assert runtime.handle_transcript("stop")["status"] == "stop_requested"
        assert rig.motor.commands[-1] == "stop"
        assert len(rig.witness.cycles) == count
    finally:
        release.set()
        runtime._worker.join(2)
    assert not runtime._worker.is_alive()
    assert results[0]["status"] == "aborted"
    assert not nonzero(rig.motor) and rig.robot.reservation is None


def test_o1_required_conditions_match_independent_contract():
    assert set(HumanConditions.__dataclass_fields__) == set(REQUIRED_HUMAN_CONDITIONS)
    assert set(HumanConditions().failures()) == set(REQUIRED_HUMAN_CONDITIONS)


@cases("text", [
    "suis la balle de ma femme", "suis la balle jaune de mon ami",
    "follow the yellow ball of my friend",
])
def test_o9_human_reference_does_not_replace_explicit_ball_target(text):
    assert not requests_human_follow(text)
    assert IntentParser().parse(text).name == "follow_object"


@cases("text", ["suivre la 2 minutes", "suis-la deux minutes"])
def test_o10_historical_object_pronoun_with_unprefixed_duration(text):
    intent = IntentParser().parse(text)
    assert intent.name == "follow_object"
    assert intent.parameters["duration_s"] == 120.0


@cases("text", [
    "suis une dame", "suis Mathieu", "suis une cible inconnue",
    "suis la balle bleue", "avance puis suis Mathieu", "follow someone",
    "suis",
])
def test_o9_unsupported_follow_target_refused_before_any_llm_or_partial_plan(text, tmp_path):
    rig = Rig(False)
    runtime = rig.runtime(tmp_path)
    runtime.use_llm = True
    with patch.object(vr, "ask_llm_for_intent", unexpected_llm):
        with patch.object(vr, "ask_llm_for_intent_plan_with_trace", unexpected_llm):
            for entry in (runtime.handle_text, runtime.handle_text_as_plan, runtime.handle_transcript):
                result = entry(text)
                assert result["status"] == "rejected"
                assert result["reason"] == "unsupported_follow_target"
    assert LanguageController(robot=rig.robot).handle_text(text)["reason"] == "unsupported_follow_target"
    assert IntentParser().parse_plan(text)[0].name == "unknown"
    assert not nonzero(rig.motor)


@cases("step", [
    {"intent": "follow_object", "target": "blue"},
    {"intent": "follow_object", "parameters": {"target_object": "person"}},
    {"intent": "follow", "target": "person", "parameters": {"target_object": "yellow"}},
    {"intent": "follow_object", "target": "yellow", "parameters": {"target_object": "blue"}},
    {"intent": "follow_red_ball", "parameters": {"target_object": "person"}},
    {"intent": "execute_path", "parameters": {"path": [
        {"action": "follow_object", "target": "blue", "parameters": []},
    ]}},
])
def test_o9_raw_unsupported_llm_target_never_filtered_or_repaired(step, tmp_path):
    rig = Rig(False)
    runtime = rig.runtime(tmp_path)
    runtime.use_llm = True
    content = json.dumps({"steps": [{"intent": "move_forward"}, step]})
    with patch.object(vr, "_post_llm_chat", return_value=content):
        result = runtime.handle_text_as_plan("avance")
    assert result["status"] == "rejected"
    assert result["reason"] == "unsupported_follow_target"
    assert not nonzero(rig.motor)


def test_o9_internal_unsupported_target_cannot_be_overwritten_by_valid_color(tmp_path):
    rig = Rig(False)
    runtime = rig.runtime(tmp_path)
    intent = Intent("follow_object", target="person", parameters={"target_object": "yellow"})
    normalized = runtime._normalize_plan_intent_names([intent])[0]
    assert normalized.target == "person"
    assert runtime.controller.handle_intent(normalized)["status"] == "rejected"
    unknown_parameter = Intent("follow_object", parameters={"target_object": "blue"})
    assert runtime.controller.handle_intent(unknown_parameter)["status"] == "rejected"
    assert not runtime.validator.validate(
        Intent("follow_red_ball", parameters={"target_object": "person"})
    )
    runtime.use_llm = True
    with patch.object(vr, "_post_llm_chat", return_value=json.dumps({
        "intent": "follow_object", "target": "blue",
    })):
        assert runtime.handle_text("avance")["status"] == "rejected"
    assert not nonzero(rig.motor)


@cases("threaded", [False, True])
def test_o7_transcript_observing_first_armament_is_not_admitted(threaded, tmp_path):
    rig = Rig()
    runtime = rig.runtime(tmp_path)
    runtime.threaded = threaded
    rig.robot.priority_one("P1")
    rig.clock.now = 2.0
    rig.p5.transition("inhibited", "after-interrupt", "P1")
    runtime.supervise_once()
    rig.clock.now = 3.0
    rig.p5.transition("armed", "new-armament")

    def request():
        result = runtime.handle_transcript("avance pendant 1 seconde")
        if threaded and runtime._worker is not None:
            runtime._worker.join(2)
            assert not runtime._worker.is_alive(), "transcript worker did not finish"
            result = runtime.last_result
        return result

    first = request()
    assert first["status"] == "aborted" and "rearm_required" in first["causes"]
    assert not nonzero(rig.motor) and rig.robot.reservation is None
    assert request()["status"] == "accepted"
    assert nonzero(rig.motor) == ["forward"]


def test_o7_queued_transcript_cannot_survive_new_interrupt_and_armament(tmp_path):
    rig = Rig()
    runtime = rig.runtime(tmp_path)
    runtime.threaded = True
    entered = threading.Event()
    release = threading.Event()
    original_worker = runtime._mission_worker

    def delayed_worker(*args, **kwargs):
        entered.set()
        if not release.wait(2):
            raise AssertionError("controlled admission wait timed out")
        original_worker(*args, **kwargs)

    runtime._mission_worker = delayed_worker
    runtime.handle_transcript("avance pendant 1 seconde")
    try:
        assert entered.wait(2), "queued request observer unavailable"
        rig.robot.priority_one("P6")
        rig.clock.now = 2.0
        rig.p5.transition("inhibited", "queued-off", "P6")
        rig.robot.supervise()
        rig.clock.now = 3.0
        rig.p5.transition("armed", "queued-new-arm")
        rig.robot.supervise()
    finally:
        release.set()
        runtime._worker.join(2)
    assert not runtime._worker.is_alive()
    assert runtime.last_result["status"] == "aborted"
    assert not nonzero(rig.motor) and rig.robot.reservation is None


@cases("command", ["backward", "backward_for"])
def test_o1_human_backward_forbidden_even_with_all_conditions_true(command):
    rig = Rig()
    permit = rig.human()
    motion = getattr(rig.robot.bind(permit), command)
    with expect_error(ProtectionFault, match="human_backward_forbidden"):
        motion(0.1) if command.endswith("_for") else motion()
    assert not nonzero(rig.motor)
    assert rig.motor.commands[-1] == "stop"
    assert rig.robot.reservation.phase == "suspended"
    assert rig.witness.requests == ["startup"]


@cases("event", ["stop", "deadline"])
def test_o6_known_stop_precedes_blocked_conditions(event):
    rig = Rig()
    permit = rig.human()
    rig.robot.bind(permit).forward()
    if event == "deadline":
        rig.clock.now = 7.0
        rig.p5.refresh()
    entered = threading.Event()
    release = threading.Event()
    errors = []

    def conditions():
        entered.set()
        if not release.wait(2):
            raise AssertionError("controlled conditions wait timed out")
        return replace(rig.facts, output_audio_ready=False)

    def cycle():
        try:
            rig.robot.supervise(events=("stop",) if event == "stop" else ())
        except Exception as exc:
            errors.append(exc)

    rig.condition_hook = conditions
    before = len(rig.witness.cycles)
    worker = threading.Thread(target=cycle, name="isolated-known-stop")
    worker.start()
    try:
        assert entered.wait(2), "conditions observer unavailable"
        assert rig.motor.commands[-1] == "stop", "zero must precede callback"
        assert rig.robot.reservation.phase == "ended"
        assert not rig.robot.valid_result(permit)
        assert len(rig.witness.cycles) == before
    finally:
        release.set()
        worker.join(2)
    assert not worker.is_alive() and not errors
    assert rig.robot.reservation.phase == "ended"
    assert set(rig.robot.causes) >= {event, "output_audio_ready"}
    assert nonzero(rig.motor) == ["forward"]
    assert rig.witness.requests == ["startup"]


@cases("fail_zero,fail_request", [(True, False), (True, True), (False, True)])
def test_o5_startup_attempts_both_outputs_and_preserves_errors(fail_zero, fail_request):
    clock = Clock()
    witness = Witness()
    motor = Motor(witness)
    motor.fail_stop = fail_zero
    witness.fail_request = fail_request
    attempts = []
    original_request = witness.request

    def request(cause):
        attempts.append(cause)
        original_request(cause)

    witness.request = request
    try:
        RobotController(
            motor, clock.time, clock.sleep, protection="present",
            ports=ProtectionPorts(P5(clock), witness, witness, 0.25, witness),
        )
    except ExceptionGroup as exc:
        assert fail_zero and fail_request
        assert {str(error) for error in exc.exceptions} == {
            "scripted zero output failure", "scripted inhibition port",
        }
    except OSError as exc:
        assert fail_zero != fail_request
        assert str(exc) == (
            "scripted zero output failure" if fail_zero else "scripted inhibition port"
        )
    else:
        raise AssertionError("startup output failure was hidden")
    assert attempts == ["startup"]
    assert ("zero_attempted", None) in witness.events
    assert not witness.cycles


@cases("present", [False, True])
def test_o10_listen_once_uses_only_explicit_audio_and_transcript_doubles(present, tmp_path):
    rig = Rig(present)
    runtime = rig.runtime(tmp_path)
    audio = sys.modules["irobot.hardware.audio.audio_utils"]
    with patch.object(audio, "resolve_input_device", return_value="fictional-input") as resolve:
        with patch.object(vr, "transcribe_loop", return_value=iter(["stop"])) as transcribe:
            result = runtime.listen_once()
    resolve.assert_called_once_with("auto")
    transcribe.assert_called_once_with("fictional-input")
    assert result["status"] == "accepted"
    assert not nonzero(rig.motor) and rig.motor.commands[-1] == "stop"


def test_o12_wall_bound_is_not_a_catchable_business_exception():
    from tests.isolated import run_lot_a as harness

    rig = Rig(False)
    context = SkillContext(
        robot=rig.robot, perception=SimpleNamespace(detect=lambda **_: harness.timeout()),
    )
    skill = FollowObjectSkill(
        settings=RuntimeSettings(), time_fn=rig.clock.time, sleep_fn=rig.clock.sleep,
    )
    before = len(harness.VIOLATIONS)
    with expect_error(harness.CampaignTimeout, match="120 s"):
        skill.execute(context)
    assert len(harness.VIOLATIONS) == before + 1
    assert not issubclass(harness.CampaignTimeout, Exception)
    assert rig.motor.commands[-1] == "stop"
    harness.VIOLATIONS.pop()


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, function in sorted(globals().copy().items()):
        if not name.startswith("test_") or not callable(function):
            continue
        axes = getattr(function, "axes", [])
        rows = [dict()]
        for names, values in axes:
            rows = [
                {**row, **dict(zip(names, (value,) if len(names) == 1 else value))}
                for row, value in product(rows, values)
            ]
        for index, row in enumerate(rows):
            def invoke(function=function, row=row):
                with tempfile.TemporaryDirectory(prefix="lot-a-case-") as directory:
                    arguments = dict(row)
                    if "tmp_path" in inspect.signature(function).parameters:
                        arguments["tmp_path"] = Path(directory)
                    function(**arguments)
            suite.addTest(unittest.FunctionTestCase(invoke, description=f"{name}[{index}]"))
    return suite
