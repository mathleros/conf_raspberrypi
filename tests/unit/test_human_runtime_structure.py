"""Human-follow extraction limits and compatibility, without concrete hardware."""

import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from irobot.interfaces import human_perception, human_perception_contracts
from irobot.interfaces.aruco_marker_decoder import OpenCVArucoMarkerDecoder
from irobot.interfaces.human_follow_announcements import HumanAnnouncement
from irobot.interfaces.human_follow_runtime import HumanAnnouncement as PublicAnnouncement
from irobot.interfaces.human_perception import HumanMarkerAcquisition
from tests.unit.test_human_perception import FakeArucoApi


PACKAGE = Path(__file__).resolve().parents[2] / "src/irobot"
LOGIC_FILES = (
    "interfaces/human_follow_runtime.py",
    "interfaces/human_follow_perception.py",
    "interfaces/human_follow_announcements.py",
    "interfaces/human_perception.py",
    "interfaces/human_perception_contracts.py",
    "interfaces/aruco_marker_decoder.py",
)
BACKEND_FILE = "hardware/camera/aruco_backend.py"


class HumanRuntimeStructureTests(unittest.TestCase):
    def test_modules_and_functions_respect_line_limits(self):
        for name in (*LOGIC_FILES, BACKEND_FILE):
            source = (PACKAGE / name).read_text(encoding="utf-8")
            with self.subTest(module=name):
                self.assertLessEqual(len(source.splitlines()), 500)
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start = min([node.lineno] + [item.lineno for item in node.decorator_list])
                    with self.subTest(module=name, function=node.name):
                        self.assertLessEqual(node.end_lineno - start + 1, 50)

    def test_concrete_import_is_limited_to_lazy_backend_loader(self):
        forbidden = ("irobot.hardware", "gpiozero", "RPi", "cv2", "picamera", "vosk")
        for name in LOGIC_FILES:
            tree = ast.parse((PACKAGE / name).read_text(encoding="utf-8"))
            allowed = set()
            if name == "interfaces/aruco_marker_decoder.py":
                loader = next(node for node in ast.walk(tree)
                              if isinstance(node, ast.FunctionDef) and node.name == "_load_aruco_api")
                allowed = {id(node) for node in ast.walk(loader)}
            for node in ast.walk(tree):
                imports = []
                if isinstance(node, ast.Import):
                    imports = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imports = [node.module or ""]
                concrete = [module for module in imports if module.startswith(forbidden)]
                if concrete:
                    with self.subTest(module=name, line=node.lineno):
                        self.assertIn(id(node), allowed)
                        self.assertEqual(concrete, ["irobot.hardware.camera.aruco_backend"])

    def test_public_contracts_and_decoder_keep_their_identity(self):
        names = (
            "AcquisitionAssessment", "AcquisitionReason", "AcquisitionStatus",
            "ArucoDetectorBackend", "ArucoFrameDetection", "HumanMarkerMissionContext",
            "HumanPerceptionFrame", "HumanPerceptionFrameSource", "HumanPerceptionProvider",
            "HumanPerceptionStreamFault", "MarkerObservation", "MarkerQuality",
            "ObservationDisposition",
        )
        for name in names:
            with self.subTest(symbol=name):
                self.assertIs(getattr(human_perception, name),
                              getattr(human_perception_contracts, name))
        self.assertIs(human_perception.OpenCVArucoMarkerDecoder, OpenCVArucoMarkerDecoder)
        self.assertIs(PublicAnnouncement, HumanAnnouncement)
        identity = human_perception.MarkerIdentity("aruco", "DICT_4X4_50", "1")
        context = human_perception_contracts.HumanMarkerMissionContext("mission", "context", identity)
        acquisition = context.new_acquisition(max_age_seconds=0.2)
        self.assertIs(type(acquisition), HumanMarkerAcquisition)
        self.assertEqual(acquisition.expected_identity, identity)
        self.assertEqual((acquisition.mission_id, acquisition.context_version), ("mission", "context"))

    def test_injected_aruco_api_never_loads_concrete_backend(self):
        identity = human_perception.MarkerIdentity("aruco", "DICT_4X4_50", "1")
        with patch.object(OpenCVArucoMarkerDecoder, "_load_aruco_api",
                          side_effect=AssertionError("unexpected hardware")) as load:
            decoder = OpenCVArucoMarkerDecoder(identity, aruco_api=FakeArucoApi())
            result = decoder.detect(object())
        load.assert_not_called()
        self.assertIs(result.disposition, human_perception.ObservationDisposition.ABSENT)

    def test_default_aruco_api_loads_only_on_decoder_construction(self):
        identity = human_perception.MarkerIdentity("aruco", "DICT_4X4_50", "1")
        with patch.object(OpenCVArucoMarkerDecoder, "_load_aruco_api",
                          return_value=FakeArucoApi()) as load:
            decoder = OpenCVArucoMarkerDecoder(identity)
        load.assert_called_once_with()
        self.assertEqual(decoder.identity, identity)
        with patch.object(OpenCVArucoMarkerDecoder, "_load_aruco_api", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "OpenCV ArUco API is unavailable"):
                OpenCVArucoMarkerDecoder(identity)
