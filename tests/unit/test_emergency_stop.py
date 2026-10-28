from __future__ import annotations

import threading
import time

from irobot.config.settings import RuntimeSettings
from irobot.domain.skills import SkillContext
from irobot.domain.skills.behaviors.follow_object import FollowObjectSkill
from irobot.interfaces.robot_controller import RobotController
from irobot.interfaces.voice_runtime import VoiceRuntime
from tests.unit.fake_robot import FakeRobot
from tests.unit.test_follow_object import World


def test_controller_event_and_underlying_detector():
    fake = FakeRobot()
    controller = RobotController(fake)
    assert controller.is_emergency_stop_requested() is False

    controller.request_emergency_stop()
    assert controller.is_emergency_stop_requested() is True
    assert controller._is_emergency_stop_requested() is True
    assert fake.commands[-1] == "stop"

    controller.clear_emergency_stop()
    assert controller.is_emergency_stop_requested() is False

    fake.stop_requested = True
    assert controller.is_emergency_stop_requested() is True


def test_stop_from_other_thread_interrupts_follow_object():
    world = World(distance_cm=100.0)
    controller = RobotController(world)
    started = threading.Event()

    def sleep(seconds: float) -> None:
        world.now += seconds
        started.set()
        time.sleep(0.0005)

    context = SkillContext(robot=controller, perception=world, state={"active_intent_parameters": {"duration_s": 300}})
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
        super().__init__(use_llm=False, **kwargs)
        self.texts: list[str] = []
        self.entered = threading.Event()
        self.flag_at_start: bool | None = None

    def handle_text_as_plan(self, text):
        self.texts.append(text)
        self.flag_at_start = self.robot.is_emergency_stop_requested()
        self.entered.set()
        deadline = time.monotonic() + 5
        while not self.robot.is_emergency_stop_requested() and time.monotonic() < deadline:
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
    assert controller.is_emergency_stop_requested() is True
    assert runtime.texts == ["suis la balle"]


def test_non_stop_phrase_ignored_during_mission(capsys):
    controller = RobotController(FakeRobot())
    runtime = BlockingRuntime(robot=controller)

    runtime.handle_transcript("suis la balle")
    assert runtime.entered.wait(2)
    runtime.handle_transcript("avance de deux mètres")

    assert runtime.texts == ["suis la balle"]
    assert controller.is_emergency_stop_requested() is False
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
    runtime = VoiceRuntime(robot=RobotController(FakeRobot()), use_llm=False, threaded=False)
    result = runtime.handle_transcript("stop maintenant")
    assert result["status"] == "accepted"
    assert not runtime.mission_running()
