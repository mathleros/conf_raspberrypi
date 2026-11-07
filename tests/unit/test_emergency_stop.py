from __future__ import annotations

import threading
import time

import pytest

from irobot.common.config.settings import RuntimeSettings
from irobot.common.domain.perception import PerceptionTarget
from irobot.common.domain.skills import SkillContext
from irobot.common.domain.skills.behaviors.follow_object import FollowObjectSkill
from irobot.common.interfaces.robot_controller import RobotController
from irobot.app.interfaces.voice_runtime import VoiceRuntime
from tests.unit.fake_robot import FakeRobot
from tests.unit.test_follow_object import World



def test_controller_event_and_underlying_detector():
    fake = FakeRobot()
    controller = RobotController(fake)
    assert controller.emergency_stop_requested() is False

    controller.request_emergency_stop()
    assert controller.emergency_stop_requested() is True
    assert fake.commands[-1] == "stop"

    controller.clear_emergency_stop()
    assert controller.emergency_stop_requested() is False

    fake.stop_requested = True
    assert controller.emergency_stop_requested() is True


@pytest.mark.parametrize("params", [{}, {"duration_s": 300}])
def test_stop_from_other_thread_interrupts_follow_object(params):
    world = World(distance_cm=100.0)
    controller = RobotController(world)
    started = threading.Event()

    def sleep(seconds: float) -> None:
        world.now += seconds
        started.set()
        time.sleep(0.0005)

    context = SkillContext(
        robot=controller,
        perception=world,
        perception_target=PerceptionTarget.RED_BALL,
        state={"active_intent_parameters": params},
    )
    skill = FollowObjectSkill(settings=RuntimeSettings(), time_fn=world.time, sleep_fn=sleep)

    def stopper():
        started.wait(5)
        controller.request_emergency_stop()

    thread = threading.Thread(target=stopper)
    thread.start()
    result = skill.execute(context)
    thread.join()

    assert result.data["emergency_stop"] is True
    assert world.now < 300
    assert world.commands[-1] == "stop"


class BlockingRuntime(VoiceRuntime):
    def __init__(self, **kwargs):
        super().__init__(use_llm=False, wake_word="", **kwargs)
        self.texts: list[str] = []
        self.entered = threading.Event()
        self.flag_at_start: bool | None = None

    def handle_text_as_plan(self, text):
        self.texts.append(text)
        self.flag_at_start = self.robot.emergency_stop_requested()
        self.entered.set()
        deadline = time.monotonic() + 5
        while not self.robot.emergency_stop_requested() and time.monotonic() < deadline:
            time.sleep(0.001)
        return {"status": "done"}


def test_new_mission_clears_flag_and_stop_phrase_aborts():
    controller = RobotController(FakeRobot())
    controller.request_emergency_stop()
    runtime = BlockingRuntime(robot=controller)

    runtime.handle_transcript("suis la balle")
    assert runtime.entered.wait(2)
    assert runtime.flag_at_start is False

    runtime.handle_transcript("arrête-toi")
    runtime._worker.join(2)
    assert not runtime.mission_running()
    assert controller.emergency_stop_requested() is True
    assert runtime.texts == ["suis la balle"]


def test_non_stop_phrase_ignored_during_mission(capsys):
    controller = RobotController(FakeRobot())
    runtime = BlockingRuntime(robot=controller)

    runtime.handle_transcript("suis la balle")
    assert runtime.entered.wait(2)
    runtime.handle_transcript("avance de deux mètres")

    assert runtime.texts == ["suis la balle"]
    assert controller.emergency_stop_requested() is False
    assert "ignorée" in capsys.readouterr().out
    runtime.close()


def test_close_stops_robot_and_joins_worker():
    fake = FakeRobot()
    runtime = BlockingRuntime(robot=RobotController(fake))
    runtime.handle_transcript("suis la balle")
    assert runtime.entered.wait(2)

    runtime.close()

    assert not runtime.mission_running()
    assert fake.commands[-1] == "stop"


def test_sync_path_runs_inline():
    runtime = VoiceRuntime(robot=RobotController(FakeRobot()), use_llm=False, threaded=False, wake_word="")
    result = runtime.handle_transcript("stop maintenant")
    assert result is None
    assert runtime.command_service.mission_orchestrator.state_machine.state.phase == "aborted"
    assert runtime.robot.emergency_stop_requested()
    assert not runtime.mission_running()


@pytest.mark.parametrize("text", [
    "STOP !", "arrête-toi", "halte maintenant", "pause",
    "avance puis stop et recule", "suis un chat mais arrête",
])
@pytest.mark.parametrize("threaded", [False, True])
def test_stop_is_immediate_even_without_a_mission(tmp_path, monkeypatch, text, threaded):
    fake = FakeRobot()
    runtime = VoiceRuntime(robot=fake, trace_dir=str(tmp_path), threaded=threaded, wake_word="")
    calls = []
    original_request = runtime._request_emergency_stop

    def request():
        calls.append("request")
        original_request()

    monkeypatch.setattr(runtime, "_request_emergency_stop", request)
    monkeypatch.setattr(runtime.command_service.parser, "parse", lambda _: pytest.fail("parser called"))
    monkeypatch.setattr(runtime.command_service, "_ask_plan", lambda _: pytest.fail("LLM called"))
    assert runtime.handle_transcript(text) is None
    assert calls == ["request"]
    assert fake.commands[0] == "stop"
    assert runtime.command_service._emergency_stop_requested()
    assert runtime.command_service.mission_orchestrator.state_machine.state.phase == "aborted"
    assert runtime._worker is None


def test_stop_during_llm_planning_prevents_all_motion(tmp_path, monkeypatch):
    from irobot.app.domain.intent import Intent

    fake = FakeRobot()
    runtime = VoiceRuntime(robot=RobotController(fake), trace_dir=str(tmp_path), wake_word="")
    entered, release = threading.Event(), threading.Event()

    def plan(_):
        entered.set()
        assert release.wait(2)
        return [Intent(name="move_forward", parameters={"duration": 1})], {"source": "llm_plan"}

    monkeypatch.setattr(runtime.command_service, "_ask_plan", plan)
    try:
        runtime.handle_transcript("avance")
        assert entered.wait(2)
        start = time.monotonic()
        runtime.handle_transcript("stop puis recule")
        assert time.monotonic() - start < 0.1
        assert fake.commands[-1] == "stop"
    finally:
        release.set()
        runtime.close()
    assert runtime.last_result["status"] == "aborted"
    assert runtime.last_result["steps"] == []
    assert "forward" not in fake.commands
    assert not runtime.mission_running()


def test_stop_does_not_wait_for_blocked_ultrasound(tmp_path):
    fake = FakeRobot()
    controller = RobotController(fake)
    runtime = VoiceRuntime(robot=controller, use_llm=False, trace_dir=str(tmp_path), wake_word="")
    entered, release = threading.Event(), threading.Event()

    def obstacle():
        entered.set()
        assert release.wait(2)
        return False

    fake.check_obstacle = obstacle
    try:
        runtime.handle_transcript("avance pendant cinq secondes puis recule")
        assert entered.wait(2)
        start = time.monotonic()
        runtime.handle_transcript("halte")
        assert time.monotonic() - start < 0.1
        assert fake.commands[-1] == "stop"
    finally:
        release.set()
        runtime.close()
    assert not runtime.mission_running()
    assert runtime.last_result["status"] == "aborted"
    assert "forward" not in fake.commands
    assert "backward" not in fake.commands


def test_motion_cannot_restart_after_stop_during_initial_sensor_read():
    fake = FakeRobot()
    controller = RobotController(fake)

    def obstacle():
        controller.request_emergency_stop()
        return False

    fake.check_obstacle = obstacle
    assert controller.forward_for(5) == "emergency_stop"
    assert "forward" not in fake.commands
    assert fake.commands[-1] == "stop"


def test_stop_cancels_timed_motion_and_remaining_steps(tmp_path):
    fake = FakeRobot()
    now = 0.0

    def sleep(seconds):
        nonlocal now
        now += seconds
        runtime.handle_transcript("pause")

    controller = RobotController(fake, time_fn=lambda: now, sleep_fn=sleep)
    runtime = VoiceRuntime(
        robot=controller, use_llm=False, threaded=False, trace_dir=str(tmp_path), wake_word="",
    )
    result = runtime.handle_transcript("avance pendant cinq secondes puis recule")
    assert result["status"] == "aborted"
    assert result["mission"]["phase"] == "aborted"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["attempt"] == 1
    assert now <= controller.CONTROL_LOOP_PERIOD_S
    assert fake.commands.count("forward") == 1
    assert "backward" not in fake.commands
    assert fake.commands[-1] == "stop"


@pytest.mark.parametrize("duration", [-1, float("inf"), float("nan"), True])
def test_invalid_duration_stops_and_raises(duration):
    fake = FakeRobot()
    with pytest.raises(ValueError, match="duration"):
        RobotController(fake).forward_for(duration)
    assert fake.commands == ["stop"]


def test_stop_failure_still_requests_cancellation(tmp_path, monkeypatch):
    fake = FakeRobot()
    runtime = VoiceRuntime(robot=fake, trace_dir=str(tmp_path), wake_word="")
    calls = []

    def stop():
        calls.append("stop")
        raise OSError("driver stop failed")

    def request():
        calls.append("request")
        runtime._emergency_event.set()

    monkeypatch.setattr(fake, "stop", stop)
    monkeypatch.setattr(runtime, "_request_emergency_stop", request)
    with pytest.raises(OSError, match="driver stop failed"):
        runtime.handle_transcript("stop")
    assert calls == ["stop", "request"]
    assert runtime.command_service._emergency_stop_requested()
    assert runtime.command_service.mission_orchestrator.state_machine.state.phase == "aborted"


@pytest.mark.parametrize("mode", ["error", "unavailable"])
def test_ultrasound_failure_is_logged_and_prevents_motion(caplog, mode):
    fake = FakeRobot()

    def obstacle():
        if mode == "error":
            raise OSError("sensor failed")
        return None

    fake.check_obstacle = obstacle
    assert RobotController(fake).forward_for(5) == "obstacle"
    assert fake.commands == ["stop"]
    assert caplog.records
