"""Controller extraction limits and public compatibility, without hardware."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from irobot.interfaces import RobotController
from irobot.interfaces.mission_robot import MissionRobot
from irobot.interfaces.protection import MissionPermit
from irobot.interfaces.robot_controller import MissionRobot as PublicMissionRobot


INTERFACES = Path(__file__).resolve().parents[2] / "src/irobot/interfaces"
CONTROLLER_FILES = (
    "robot_controller.py", "robot_admission.py", "robot_supervision.py",
    "robot_motion.py", "mission_robot.py",
)


class RobotControllerStructureTests(unittest.TestCase):
    def test_modules_and_functions_respect_line_limits(self):
        for name in CONTROLLER_FILES:
            source = (INTERFACES / name).read_text(encoding="utf-8")
            with self.subTest(module=name):
                self.assertLessEqual(len(source.splitlines()), 500)
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start = min([node.lineno] + [item.lineno for item in node.decorator_list])
                    with self.subTest(module=name, function=node.name):
                        self.assertLessEqual(node.end_lineno - start + 1, 50)

    def test_controller_logic_never_imports_concrete_hardware(self):
        forbidden = ("irobot.hardware", "gpiozero", "RPi", "cv2", "picamera", "vosk")
        for name in CONTROLLER_FILES:
            tree = ast.parse((INTERFACES / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                imports = []
                if isinstance(node, ast.Import):
                    imports = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imports = [node.module or ""]
                if imports:
                    with self.subTest(module=name, line=node.lineno):
                        self.assertFalse(any(module.startswith(forbidden) for module in imports))

    def test_mission_capability_keeps_public_import_and_controller_hooks(self):
        calls = []
        controller = RobotController(SimpleNamespace(
            speed=0.5, stop=lambda: calls.append("stop"),
        ))
        controller.supervise = lambda *args, **kwargs: calls.append((args, kwargs))
        permit = MissionPermit(1, 2, "synthetic", controller._generation)
        robot = controller.bind(permit)
        self.assertIs(PublicMissionRobot, MissionRobot)
        self.assertIs(type(robot), MissionRobot)
        self.assertEqual(robot.speed, 0.5)
        for name in ("forward", "backward", "left", "right"):
            getattr(robot, name)()
            self.assertEqual(calls[-1], ((permit, name), {}))
        robot.set_speed(0.4)
        self.assertEqual(calls[-1], ((permit, "set_speed", 0.4), {}))
        robot.set_speed(0)
        self.assertEqual(calls[-1], "stop")
        for name in ("robot", "_robot", "__dict__", "arbitrary_driver_method"):
            with self.subTest(attribute=name), self.assertRaises(AttributeError):
                getattr(robot, name)

    def test_timed_motion_keeps_clock_period_and_final_stop(self):
        calls = []
        now = 0.0

        def sleep(duration):
            nonlocal now
            calls.append(("sleep", duration))
            now += duration

        driver = SimpleNamespace(
            forward=lambda: calls.append("forward"),
            stop=lambda: calls.append("stop"),
            check_obstacle=lambda: False,
        )
        controller = RobotController(driver, time_fn=lambda: now, sleep_fn=sleep)
        self.assertIsNone(controller.forward_for(0.05))
        self.assertEqual(calls[0], "forward")
        self.assertEqual(calls[-1], "stop")
        waits = [duration for kind, duration in calls[1:-1]]
        self.assertEqual(len(waits), 3)
        self.assertTrue(all(0 < duration <= controller.CONTROL_LOOP_PERIOD_S for duration in waits))
        self.assertAlmostEqual(now, 0.05)
        calls.clear()

        def fail_sleep(_):
            raise OSError("sleep failed")

        controller.sleep_fn = fail_sleep
        with self.assertRaisesRegex(OSError, "sleep failed"):
            controller.forward_for(0.05)
        self.assertEqual(calls, ["forward", "stop"])
