"""Controller extraction limits and public compatibility, without hardware."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from irobot.interfaces import RobotController


INTERFACES = Path(__file__).resolve().parents[2] / "src/irobot/interfaces"
CONTROLLER_FILES = (
    "robot_controller.py",
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

    def test_controller_delegates_to_injected_driver(self):
        calls = []
        controller = RobotController(SimpleNamespace(
            speed=0.5, stop=lambda: calls.append("stop"),
            forward=lambda: calls.append("forward"),
            custom=lambda: calls.append("custom"),
        ))
        self.assertEqual(controller.speed, 0.5)
        controller.forward()
        controller.custom()
        controller.stop()
        self.assertEqual(calls, ["forward", "custom", "stop"])

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
