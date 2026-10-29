import json
from pathlib import Path

import pytest

from irobot.interfaces.robot_controller import RobotController
from irobot.interfaces.voice_runtime import VoiceRuntime
from tests.unit.fake_robot import FakeRobot


@pytest.mark.parametrize(
    ("phrase", "motion", "reason"),
    [
        ("avance pendant cinq secondes", "forward", "obstacle"),
        ("tourne à gauche pendant cinq secondes", "left", "obstacle"),
        ("tourne à droite pendant cinq secondes", "right", "obstacle"),
        ("avance pendant cinq secondes", "forward", "emergency_stop"),
        ("recule pendant cinq secondes", "backward", "emergency_stop"),
    ],
)
def test_safety_stop_during_primitive_aborts_plan_without_retry(tmp_path, phrase, motion, reason):
    now = 0.0
    fake = FakeRobot()

    def sleep(seconds):
        nonlocal now
        now += seconds
        if reason == "emergency_stop":
            controller.request_emergency_stop()

    controller = RobotController(fake, time_fn=lambda: now, sleep_fn=sleep)
    fake.check_obstacle = lambda: reason == "obstacle" and now >= 0.02 and fake.commands[-1] != "stop"
    runtime = VoiceRuntime(robot=controller, use_llm=False, trace_dir=str(tmp_path))

    result = runtime.handle_text_as_plan(phrase + " puis recule de dix centimètres")

    assert result["status"] == "aborted"
    assert result["mission"]["phase"] == "aborted"
    assert len(result["steps"]) == 1
    step = result["steps"][0]
    assert step["attempt"] == 1
    assert step["results"][0].data["motion"] == "stop"
    flag = "obstacle_detected" if reason == "obstacle" else "emergency_stop"
    assert step["results"][0].data[flag] is True
    assert fake.commands.count(motion) == 1
    assert fake.commands[-1] == "stop"
    assert fake.check_obstacle() is False
    assert now < 5
    events = [json.loads(line)["event"] for line in Path(result["trace_path"]).read_text().splitlines()]
    assert ("obstacle_stop" if reason == "obstacle" else "emergency_stop") in events


def test_initial_obstacle_is_traced_and_prevents_motion(tmp_path):
    fake = FakeRobot()
    fake.obstacle_detected = True
    runtime = VoiceRuntime(robot=RobotController(fake), use_llm=False, trace_dir=str(tmp_path))

    result = runtime.handle_text_as_plan("avance pendant cinq secondes")

    assert result["status"] == "aborted"
    assert "forward" not in fake.commands
    assert fake.commands[-1] == "stop"
    assert '"event": "obstacle_stop"' in Path(result["trace_path"]).read_text()


def test_uninterrupted_primitive_runs_full_duration(tmp_path):
    now = 0.0
    fake = FakeRobot()

    def sleep(seconds):
        nonlocal now
        now += seconds

    controller = RobotController(fake, time_fn=lambda: now, sleep_fn=sleep)
    runtime = VoiceRuntime(robot=controller, use_llm=False, trace_dir=str(tmp_path))

    result = runtime.handle_text_as_plan("avance pendant cinq secondes")

    assert result["status"] == "accepted"
    assert now == pytest.approx(5)
    assert fake.commands.count("forward") == 1
    assert fake.commands[-1] == "stop"


def test_motion_exception_still_stops_motor():
    fake = FakeRobot()

    def sleep(seconds):
        raise RuntimeError("interruption du temporisateur")

    controller = RobotController(fake, sleep_fn=sleep)
    with pytest.raises(RuntimeError, match="temporisateur"):
        controller.forward_for(5)
    assert fake.commands[-1] == "stop"
