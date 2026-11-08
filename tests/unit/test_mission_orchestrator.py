import ast
from pathlib import Path

import pytest

from irobot.common.config.settings import RuntimeSettings
from irobot.app.domain.intent import Intent
from irobot.app.domain.orchestrator.mission_orchestrator import MissionOrchestrator
from irobot.app.domain.orchestrator.planner import SkillPlanStep
from irobot.common.domain.skills.base_skill import SkillResult


def plan(*names):
    return [SkillPlanStep(Intent(name=name), ()) for name in names]


def test_sequence_and_success_without_voice_or_hardware():
    orchestrator = MissionOrchestrator()
    calls = []
    events = []

    def execute(step):
        assert orchestrator.state_machine.state.phase == "executing"
        calls.append(step.intent.name)
        return {"intent": step.intent, "status": "accepted", "results": [SkillResult()]}

    steps, status = orchestrator.execute(
        plan("move_forward", "turn_left"), execute,
        stop_requested=lambda: False, on_event=events.append,
    )

    assert calls == ["move_forward", "turn_left"]
    assert status == "accepted"
    assert [step["attempt"] for step in steps] == [1, 1]
    assert [event["event"] for event in events] == ["step_result", "step_result"]
    assert orchestrator.state_machine.as_dict()["phase"] == "success"
    assert orchestrator.state_machine.state.metadata == {"steps_total": 2, "step_index": 1}


def test_retry_recovers_before_next_step():
    orchestrator = MissionOrchestrator()
    calls = []

    def execute(step):
        calls.append(step.intent.name)
        status = "failed" if len(calls) == 1 else "success"
        return {"status": "accepted", "results": [SkillResult(status=status)]}

    steps, status = orchestrator.execute(
        plan("move_forward", "stop"), execute, stop_requested=lambda: False,
    )

    assert status == "accepted"
    assert calls == ["move_forward", "move_forward", "stop"]
    assert [step["attempt"] for step in steps] == [2, 1]


def test_exhausted_retries_fail_and_skip_remaining_steps():
    orchestrator = MissionOrchestrator(settings=RuntimeSettings(max_step_retries=1))
    calls = []

    def execute(step):
        calls.append(step.intent.name)
        return {"status": "accepted", "results": [SkillResult(status="failed")]}

    steps, status = orchestrator.execute(
        plan("move_forward", "stop"), execute, stop_requested=lambda: False,
    )

    assert calls == ["move_forward", "move_forward"]
    assert status == "incomplete"
    assert steps[0]["reason"] == "max retries reached"
    assert orchestrator.state_machine.state.phase == "failed"
    assert orchestrator.state_machine.state.metadata["failed_at"] == 0


@pytest.mark.parametrize("reason", ["emergency_stop", "obstacle_detected"])
def test_safety_stop_during_step_is_not_retried(reason):
    orchestrator = MissionOrchestrator()
    events = []

    def execute(step):
        return {"status": "accepted", "results": [SkillResult(data={reason: True})]}

    steps, status = orchestrator.execute(
        plan("move_forward", "turn_left"), execute,
        stop_requested=lambda: False, on_event=events.append,
    )

    assert status == "aborted"
    assert len(steps) == 1
    assert steps[0]["attempt"] == 1
    assert orchestrator.state_machine.state.phase == "aborted"
    assert events[-1]["event"] == ("emergency_stop" if reason == "emergency_stop" else "obstacle_stop")


def test_stop_before_execution_skips_executor():
    orchestrator = MissionOrchestrator()
    steps, status = orchestrator.execute(
        plan("move_forward"), lambda _: pytest.fail("Executor must not run"),
        stop_requested=lambda: True,
    )
    assert status == "aborted"
    assert steps[0]["reason"] == "emergency stop"
    assert orchestrator.state_machine.state.phase == "aborted"


def test_step_timeout_uses_injected_clock_and_stops_sequence():
    clock = [0.0]
    orchestrator = MissionOrchestrator(time_fn=lambda: clock[0])

    def execute(step):
        clock[0] += 7
        return {"status": "accepted"}

    steps, status = orchestrator.execute(
        plan("move_forward", "turn_left"), execute, stop_requested=lambda: False,
    )
    assert status == "aborted"
    assert len(steps) == 1
    assert steps[0]["step_duration_seconds"] == 7
    assert steps[0]["reason"] == "step timeout"


def test_mission_timeout_includes_time_spent_retrying():
    clock = [0.0]
    orchestrator = MissionOrchestrator(
        settings=RuntimeSettings(step_timeout_seconds=6, mission_timeout_seconds=0),
        time_fn=lambda: clock[0],
    )
    calls = []
    events = []

    def execute(step):
        calls.append(step.intent.name)
        clock[0] += 5
        status = "failed" if len(calls) < 3 else "success"
        return {"status": "accepted", "results": [SkillResult(status=status)]}

    steps, status = orchestrator.execute(
        plan("move_forward", "turn_left"), execute,
        stop_requested=lambda: False, on_event=events.append,
    )
    assert calls == ["move_forward"] * 3
    assert status == "aborted"
    assert steps[-1]["reason"] == "mission timeout"
    assert events[-1]["event"] == "mission_timeout"
    assert orchestrator.state_machine.state.metadata["aborted_at"] == 1


def test_execution_error_is_propagated_and_marks_mission_failed():
    orchestrator = MissionOrchestrator()

    def execute(step):
        raise OSError("motor disconnected")

    with pytest.raises(OSError, match="motor disconnected"):
        orchestrator.execute(plan("move_forward"), execute, stop_requested=lambda: False)
    assert orchestrator.state_machine.state.phase == "failed"
    assert "motor disconnected" in orchestrator.state_machine.state.last_error


def test_empty_plan_is_an_explicit_error():
    orchestrator = MissionOrchestrator()
    with pytest.raises(ValueError, match="at least one"):
        orchestrator.execute([], lambda _: pytest.fail("Executor must not run"), stop_requested=lambda: False)


def test_domain_has_no_interface_or_hardware_imports():
    root = Path(__file__).resolve().parents[2] / "src" / "irobot"
    forbidden = (
        "irobot.common.interfaces",
        "irobot.app.interfaces",
        "irobot.common.hardware",
    )
    for domain in (root / "common" / "domain", root / "app" / "domain"):
        for path in domain.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom):
                    assert not (node.module or "").startswith(forbidden), path
                elif isinstance(node, ast.Import):
                    assert all(not alias.name.startswith(forbidden) for alias in node.names), path


def _settling_orchestrator(settle_s=0.3, sleep_fn=None):
    sleeps = []
    orchestrator = MissionOrchestrator(
        settings=RuntimeSettings(motion_settle_seconds=settle_s),
        sleep_fn=sleep_fn or sleeps.append,
    )
    return orchestrator, sleeps


def _run_names(orchestrator, *names, stop_requested=lambda: False):
    return orchestrator.execute(
        plan(*names),
        lambda step: {"intent": step.intent, "status": "accepted", "results": [SkillResult()]},
        stop_requested=stop_requested,
    )


def test_motion_settle_pause_between_open_loop_moves():
    orchestrator, sleeps = _settling_orchestrator()
    _run_names(orchestrator, "move_forward", "turn_left")
    assert sum(sleeps) == pytest.approx(0.3)

    orchestrator, sleeps = _settling_orchestrator()
    _run_names(orchestrator, "move_forward", "move_forward", "turn_left")
    assert sum(sleeps) == pytest.approx(0.6)

    orchestrator, sleeps = _settling_orchestrator()
    _, status = _run_names(orchestrator, "turn_left", "move_forward", "stop")
    assert status == "accepted"
    assert sum(sleeps) == pytest.approx(0.3)

    orchestrator, sleeps = _settling_orchestrator()
    _run_names(orchestrator, "follow_object", "turn_left")
    assert sleeps == []

    orchestrator, sleeps = _settling_orchestrator(settle_s=0.0)
    _run_names(orchestrator, "move_forward", "turn_left")
    assert sleeps == []


def test_stop_requested_during_settle_aborts_before_next_step():
    flag = {"stop": False}
    executed = []
    orchestrator, _ = _settling_orchestrator(sleep_fn=lambda _: flag.update(stop=True))

    def execute(step):
        executed.append(step.intent.name)
        return {"intent": step.intent, "status": "accepted", "results": [SkillResult()]}

    _, status = orchestrator.execute(
        plan("move_forward", "turn_left"), execute, stop_requested=lambda: flag["stop"],
    )
    assert executed == ["move_forward"]
    assert status == "aborted"
