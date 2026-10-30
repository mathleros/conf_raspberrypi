"""Independent offline contract runnable against HEAD and the modified source.

This does not replace or emulate the historical pytest tests.
All time/distance inputs are synthetic, not calibrated robot parameters.
"""

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from irobot.config.settings import RuntimeSettings
from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.domain.skills.behaviors.follow_object import FollowObjectSkill
from irobot.interfaces.robot_controller import RobotController
from irobot.interfaces.voice_runtime import VoiceRuntime
from tests.unit.fake_robot import FakeRobot


class LegacyContract(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="lot-a-legacy-")
        self.addCleanup(self.directory.cleanup)
        self.now = 0.0
        self.motor = FakeRobot()
        original_set_speed = self.motor.set_speed

        def speed(value):
            self.motor.commands.append(("speed", value))
            original_set_speed(value)

        self.motor.set_speed = speed
        self.robot = RobotController(self.motor, lambda: self.now, self.sleep)
        registry = SkillRegistry.default()
        registry.register(FollowObjectSkill(
            settings=RuntimeSettings(), time_fn=lambda: self.now, sleep_fn=self.sleep,
        ))
        self.distance = 180.0
        self.targets = []

        def detect(**kwargs):
            self.targets.append(kwargs.get("target"))
            return SimpleNamespace(
                position="center", distance_cm=self.distance, label="yellow", confidence=1.0,
            )

        self.runtime = VoiceRuntime(
            robot=self.robot, perception=SimpleNamespace(detect=detect), registry=registry,
            use_llm=False, threaded=False, trace_dir=str(Path(self.directory.name)),
        )

    def sleep(self, seconds):
        self.now += seconds

    def test_exact_primitive_and_stop_outputs(self):
        cases = [
            ("avance pendant 1 seconde", ["forward", "stop", "stop"]),
            ("recule pendant 1 seconde", ["backward", "stop", "stop"]),
            ("tourne à gauche pendant 1 seconde",
             [("speed", 0.5), "left", "stop", ("speed", 0.5), "stop"]),
            ("tourne à droite pendant 1 seconde",
             [("speed", 0.5), "right", "stop", ("speed", 0.5), "stop"]),
            ("stop", ["stop", "stop"]),
        ]
        for phrase, expected in cases:
            with self.subTest(phrase=phrase):
                self.motor.commands.clear()
                before = self.now
                result = self.runtime.handle_text_as_plan(phrase)
                self.assertEqual(result["status"], "accepted")
                self.assertEqual(self.motor.commands, expected)
                self.assertAlmostEqual(self.now - before, 0 if phrase == "stop" else 1)

    def test_ball_approach_hold_backing_same_runtime(self):
        for distance, expected in [(180.0, "forward"), (100.0, None), (40.0, "backward")]:
            with self.subTest(distance=distance):
                self.distance = distance
                self.motor.commands.clear()
                result = self.runtime.handle_text_as_plan("suis la balle jaune pendant 1 seconde")
                self.assertEqual(result["status"], "accepted")
                moves = [c for c in self.motor.commands if c != "stop"]
                if expected is None:
                    self.assertEqual(moves, [])
                else:
                    self.assertTrue(moves)
                    self.assertEqual(set(moves), {expected})
                self.assertEqual(self.motor.commands[-1], "stop")
        self.assertEqual(set(self.targets), {"yellow"})

    def test_stop_during_primitive_no_next_step_or_retry(self):
        def stop_during_wait(seconds):
            self.now += seconds
            self.robot.request_emergency_stop()

        self.robot.sleep_fn = stop_during_wait
        result = self.runtime.handle_text_as_plan("avance pendant 1 seconde puis recule")
        self.assertEqual(result["status"], "aborted")
        self.assertEqual(len(result["steps"]), 1)
        self.assertEqual(result["steps"][0]["attempt"], 1)
        self.assertEqual(self.motor.commands.count("forward"), 1)
        self.assertNotIn("backward", self.motor.commands)
        self.assertEqual(self.motor.commands[-1], "stop")

    def test_invalid_full_plan_no_partial_movement(self):
        result = self.runtime.handle_text_as_plan("avance puis une commande inexistante")
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(self.motor.commands, [])
