from __future__ import annotations

import json

import pytest

from irobot.config.settings import RuntimeSettings
from irobot.domain.skills.behaviors.follow_object import FollowObjectSkill
from irobot.domain.skills.base_skill import SkillResult
from irobot.interfaces.intent_parser import Intent
from irobot.interfaces.robot_controller import RobotController
from irobot.interfaces.voice_runtime import VoiceRuntime
from tests.unit.test_follow_object import World, run


class ContinuousWorld(World):
    def __init__(self, *, stop_at=650.0, hidden=(1.0, 100.0)):
        super().__init__(distance_cm=200.0, hidden=hidden)
        self.stop_at = stop_at
        self.targets = []

    def is_emergency_stop_requested(self):
        return self.now >= self.stop_at or self.emergency

    def detect(self, target=None):
        self.targets.append(target)
        return super().detect(target)


@pytest.mark.parametrize(
    ("name", "target"),
    [("follow_person", "marker"), ("follow_red_ball", "red_ball"), ("follow_object", "yellow")],
)
def test_continuous_tracking_survives_old_limits_until_stop(tmp_path, monkeypatch, name, target):
    world = ContinuousWorld()
    runtime = VoiceRuntime(
        robot=RobotController(world, time_fn=world.time, sleep_fn=world.sleep),
        perception=world, use_llm=False, trace_dir=str(tmp_path),
    )
    runtime.settings = RuntimeSettings()
    runtime.controller.planner.registry.register(
        FollowObjectSkill(settings=runtime.settings, time_fn=world.time, sleep_fn=world.sleep)
    )
    monkeypatch.setattr("irobot.interfaces.voice_execution.time.time", world.time)
    trace_path = tmp_path / "continuous.jsonl"

    steps, status = runtime._run_plan([Intent(name=name, target=target)], trace_path)

    assert status == "aborted"
    assert steps[0]["reason"] == "emergency stop"
    assert steps[0]["attempt"] == 1
    assert steps[0]["plan"] == ["follow_object"]
    assert world.now >= 650
    assert set(world.targets) == {target}
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
        def detect(self, target=None):
            if self.now >= 1 and not getattr(self, "moved", False):
                self.distance_cm = 200
                self.moved = True
            return super().detect(target)

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

    def execute(intent):
        calls.append(intent)
        return {"status": "accepted", "results": [SkillResult(status=skill_status, message="camera error")]}

    monkeypatch.setattr(runtime.controller, "handle_intent", execute)
    result = runtime._execute_intent_with_retry(Intent(name=name), tmp_path / "failure.jsonl")

    assert result["status"] == "failed"
    assert len(calls) == 1
    assert result["results"][0].message == "camera error"


def test_continuous_tracking_requires_live_perception():
    world = World()
    runtime = VoiceRuntime(robot=world, use_llm=False)
    result = runtime.controller.handle_intent(Intent(name="follow_person", target="marker"))

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
