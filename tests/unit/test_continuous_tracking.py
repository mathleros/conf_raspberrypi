from __future__ import annotations

import json

import pytest

from irobot.app.config.settings import RuntimeSettings
from irobot.app.domain.intent import Intent
from irobot.app.domain.perception import PerceptionTarget
from irobot.app.domain.skills.behaviors.follow_object import FollowObjectSkill
from irobot.app.domain.skills.base_skill import SkillResult
from irobot.app.interfaces.robot_controller import RobotController
from irobot.app.interfaces.voice_runtime import VoiceRuntime

from tests.unit.test_follow_object import World, run


class ContinuousWorld(World):
    def __init__(self, *, stop_at=650.0, hidden=(1.0, 100.0)):
        super().__init__(distance_cm=200.0, hidden=hidden)
        self.stop_at = stop_at
        self.targets = []

    def emergency_stop_requested(self):
        return self.now >= self.stop_at or self.emergency

    def detect(self, *, target):
        self.targets.append(target)
        return super().detect(target=target)


@pytest.mark.parametrize(
    ("name", "target"),
    [("follow_person", "marker"), ("follow_red_ball", "red_ball"), ("follow_object", "yellow")],
)
def test_continuous_tracking_survives_old_limits_until_stop(tmp_path, monkeypatch, name, target):
    world = ContinuousWorld()
    runtime = VoiceRuntime(
        robot=RobotController(world, time_fn=world.time, sleep_fn=world.sleep),
        perception=world,
        use_llm=False,
        trace_dir=str(tmp_path),
    )
    runtime.command_service.settings = RuntimeSettings(
        min_stand_off_cm=10.0, stand_off_default_cm=20.0, stand_off_tolerance_percent=50.0,
    )
    runtime.command_service.controller.planner.registry.register(
        FollowObjectSkill(settings=runtime.command_service.settings, time_fn=world.time, sleep_fn=world.sleep)
    )
    runtime.command_service.mission_orchestrator.time_fn = world.time
    trace_path = tmp_path / "continuous.jsonl"

    planned = runtime.command_service.planner.plan_intents(
        [Intent(name=name, target=target)]
    )
    steps, status = runtime.command_service.mission_orchestrator.execute(
        planned, runtime.command_service.controller.handle_planned_step,
        stop_requested=runtime.command_service._emergency_stop_requested,
        on_event=lambda event: runtime.command_service._trace_mission_event(trace_path, event),
    )

    assert status == "aborted"
    assert steps[0]["reason"] == "emergency stop"
    assert steps[0]["attempt"] == 1
    assert steps[0]["plan"] == ["follow_object"]
    assert world.now >= 650
    assert set(world.targets) == {PerceptionTarget.from_value(target)}
    assert "right" in world.commands
    assert "forward" in world.commands
    assert world.commands[-1] == "stop"
    events = [json.loads(line) for line in trace_path.read_text().splitlines()]
    assert len([event for event in events if event["event"] == "step_result"]) == 1
    assert events[0]["results"][0]["data"]["emergency_stop"] is True


def test_permanently_missing_target_keeps_searching_until_stop():
    world = ContinuousWorld(stop_at=100, hidden=(0, 1000))
    result, _ = run(world)

    assert result.data["emergency_stop"] is True
    assert world.now >= 100
    assert "right" in world.commands
    assert "forward" not in world.commands
    assert world.commands[-1] == "stop"


def test_continuous_follow_resumes_after_holding_distance():
    class RecedingWorld(ContinuousWorld):
        def detect(self, *, target):
            if self.now >= 1 and not getattr(self, "moved", False):
                self.distance_cm = 200
                self.moved = True
            return super().detect(target=target)

    world = RecedingWorld(stop_at=3, hidden=(0, 0))
    world.distance_cm = 100
    result, _ = run(world)

    assert world.commands[0] == "stop"
    assert "forward" in world.commands
    assert result.data["emergency_stop"] is True


@pytest.mark.parametrize("name", ["follow_person", "follow_red_ball", "follow_object"])
@pytest.mark.parametrize("skill_status", ["failed", "in_progress"])
def test_tracking_failure_is_not_retried(tmp_path, monkeypatch, name, skill_status):
    runtime = VoiceRuntime(robot=World(), use_llm=False)
    calls = []

    def execute(step):
        calls.append(step.intent)
        return {"status": "accepted", "results": [SkillResult(status=skill_status, message="camera error")]}

    monkeypatch.setattr(runtime.command_service.controller, "handle_planned_step", execute)
    planned = runtime.command_service.planner.plan_intents([Intent(name=name)])[0]
    steps, _ = runtime.command_service.mission_orchestrator.execute(
        [planned], execute, stop_requested=lambda: False,
    )
    result = steps[0]

    assert result["status"] == "failed"
    assert len(calls) == 1
    assert result["results"][0].message == "camera error"


def test_continuous_tracking_requires_live_perception():
    world = World()
    runtime = VoiceRuntime(robot=world, use_llm=False)
    controller = runtime.command_service.controller
    step = controller.planner.plan_intents([Intent(name="follow_person", target="marker")])[0]
    result = controller.handle_planned_step(step)

    assert result["results"][0].status == "failed"
    assert "perception" in result["results"][0].data["error"]
    assert set(world.commands) == {"stop"}


def test_continuous_tracking_stops_on_obstacle():
    world = ContinuousWorld()
    world.obstacle_detected = True
    result, _ = run(world)

    assert result.data["obstacle_detected"] is True
    assert world.now == 0
    assert set(world.commands) == {"stop"}


def test_continuous_tracking_stops_on_camera_error():
    world = ContinuousWorld()
    world.detect_error = RuntimeError("camera down")
    result, _ = run(world)

    assert result.status == "failed"
    assert result.data["error"] == "camera down"
    assert set(world.commands) == {"stop"}
