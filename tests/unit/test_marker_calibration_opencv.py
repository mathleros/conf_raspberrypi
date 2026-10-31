"""Explicit native OpenCV test on synthetic points only; not part of lot A."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from irobot.interfaces.marker_calibration import ACQUISITION, SCHEMA, calibrate_views, main, marker_poses, write_record
from tests.unit.test_marker_calibration import calibration_document


class SyntheticCalibrationOpenCVTests(unittest.TestCase):
    def setUp(self):
        self.matrix = np.array([[600., 0., 240.], [0., 610., 320.], [0., 0., 1.]])
        self.distortion = np.array([0.01, -0.005, 0.001, -0.001, 0.])
        self.args = argparse.Namespace(
            rows=6, columns=9, square_cm=2., mounting="synthetic-only", revision="synthetic",
        )

    def test_intrinsics_recovery_and_holdout_without_images(self):
        board = np.zeros((54, 3), np.float32)
        board[:, :2] = np.mgrid[0:9, 0:6].T.reshape(-1, 2) * 2
        views = []
        for index in range(20):
            rotation = np.array([0.08 * (index % 5 - 2), 0.1 * (index % 4 - 1.5), 0.03 * index])
            translation = np.array([-8. + index % 4, -6. + index % 3, 50. + 2 * index])
            points, _ = cv2.projectPoints(board, rotation, translation, self.matrix, self.distortion)
            views.append(points)
        result = calibrate_views(views, self.args, cv2, np)
        np.testing.assert_allclose(result["camera_matrix"], self.matrix, atol=0.03)
        self.assertEqual(len(result["holdout_view_errors_px"]), 4)
        self.assertLess(max(result["holdout_view_errors_px"]), 0.001)
        self.assertFalse(result["sh03_qualified"])
        self.assertEqual(result["acquisition"], ACQUISITION)
        with self.assertRaises(ValueError):
            calibrate_views(views[:11], self.args, cv2, np)

    def test_square_pose_candidates_not_clearance_or_arbitrary_selection(self):
        square = np.array([[-4., 4., 0.], [4., 4., 0.], [4., -4., 0.], [-4., -4., 0.]])
        translation = np.array([2., 3., 150.])
        points, _ = cv2.projectPoints(
            square, np.array([0.2, 0.1, 0.05]), translation, self.matrix, self.distortion,
        )
        calibration = {"camera_matrix": self.matrix.tolist(), "distortion": self.distortion.tolist()}
        candidates = marker_poses(points.reshape(4, 2), 8, calibration, cv2, np)
        self.assertEqual(len(candidates), 2)
        best = min(candidates, key=lambda item: item["reprojection_rms_px"])
        self.assertAlmostEqual(best["optical_range_cm"], np.linalg.norm(translation), places=5)
        self.assertNotIn("robot_clearance_cm", best)

    def test_offline_solve_combines_prepositioned_checkerboard_sessions(self):
        board = np.zeros((54, 3), np.float32)
        board[:, :2] = np.mgrid[0:9, 0:6].T.reshape(-1, 2) * 2
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index in range(12):
                points, _ = cv2.projectPoints(
                    board, np.array([0.08 * (index % 5 - 2), 0.1 * (index % 4 - 1.5), 0.03 * index]),
                    np.array([-8. + index % 4, -6. + index % 3, 50. + 2 * index]),
                    self.matrix, self.distortion,
                )
                path = Path(directory) / f"view-{index}.jsonl"
                with path.open("x") as stream:
                    write_record(stream, {
                        "type": "run", "schema": SCHEMA, "mode": "calibrate",
                        "acquisition": ACQUISITION, "revision": "synthetic", "mounting": "synthetic-only",
                        "parameters": {"columns": 9, "rows": 6, "square_cm": 2},
                    })
                    write_record(stream, {
                        "type": "frame", "sensor_timestamp_ns": index + 100,
                        "capture_status": "new_capture", "disposition": "valid",
                        "selected_for_calibration": True, "corners_px": points.reshape(-1, 2).tolist(),
                    })
                    write_record(stream, {"type": "summary", "termination": "operator_stop"})
                paths.append(str(path))
            output = Path(directory) / "intrinsics.json"
            with patch.dict(sys.modules, {"picamera2": None}), patch("sys.stdout", new=io.StringIO()):
                result = main([
                    "solve", "--output", str(output), "--traces", *paths,
                    "--columns", "9", "--rows", "6", "--square-cm", "2",
                    "--mounting", "synthetic-only", "--revision", "synthetic",
                ])
            self.assertEqual(result, 0)
            data = json.loads(output.read_text())
            self.assertEqual(len(data["source_traces"]), 12)
            np.testing.assert_allclose(data["camera_matrix"], self.matrix, atol=0.05)

    def test_live_record_under_camera_double_retains_absence_and_closes_resources(self):
        self.run_camera_double()

    def test_operator_stop_retains_partial_calibration_without_false_success(self):
        self.run_camera_double(calibrate=True)

    def run_camera_double(self, *, calibrate=False):
        events = []
        class Request:
            def __init__(self, stamp):
                self.stamp = stamp

            def get_metadata(self):
                return {"SensorTimestamp": self.stamp, "ExposureTime": 10000, "AnalogueGain": 1.0}

            def make_array(self, _):
                return np.zeros((480, 640, 3), dtype=np.uint8)

            def release(self):
                events.append("release")

        class Camera:
            @staticmethod
            def global_camera_info():
                return [{"Model": "ov5647", "Num": 0}]

            def __init__(self, index):
                events.append(("open", index))
                self.timestamps = iter((100, 100, 200, 300))

            def create_preview_configuration(self, **kwargs):
                return kwargs

            def configure(self, config):
                self.config = config

            def camera_configuration(self):
                return {**self.config, "transform": types.SimpleNamespace(
                    hflip=False, vflip=False, transpose=False,
                )}

            def start(self):
                events.append("start")

            def capture_request(self):
                return Request(next(self.timestamps))

            def stop(self):
                events.append("stop")

            def close(self):
                events.append("close")

        picamera = types.ModuleType("picamera2")
        picamera.Picamera2 = Camera
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.jsonl"
            intrinsics = Path(directory) / "intrinsics.json"
            arguments = [
                "calibrate" if calibrate else "record", "--output", str(trace),
                "--revision", "synthetic", "--mounting", "fixture-A",
                "--authorized-camera", "--motors-isolated", "--zone-empty",
            ]
            if calibrate:
                arguments += ["--columns", "9", "--rows", "6", "--square-cm", "2",
                              "--calibration-output", str(intrinsics)]
            else:
                intrinsics.write_text(json.dumps(calibration_document()))
                arguments += ["--calibration", str(intrinsics), "--marker-cm", "8",
                              "--condition", "synthetic absence", "--frames", "3"]
            with patch.dict(sys.modules, {"picamera2": picamera}), \
                    patch.dict("os.environ", {"DISPLAY": "synthetic-only"}), \
                    patch("importlib.metadata.version", return_value="synthetic"), \
                    patch.object(cv2, "imshow"), patch.object(cv2, "destroyAllWindows"), \
                    patch.object(cv2, "waitKey", return_value=ord("q") if calibrate else -1), \
                    patch("sys.stdout", new=io.StringIO()), patch("sys.stderr", new=io.StringIO()):
                result = main(arguments)
            self.assertEqual(result, 2 if calibrate else 0)
            records = [json.loads(line) for line in trace.read_text().splitlines()]
            summary = records[-1]
            if calibrate:
                self.assertEqual(summary["termination"], "operator_stop")
                self.assertEqual(intrinsics.read_text(), "")
            else:
                self.assertEqual(summary["new_frames"], 3)
                self.assertEqual(summary["counts"]["absent"], 3)
                self.assertEqual(summary["counts"]["repeated_capture"], 1)
                self.assertEqual(summary["detected_fraction"], 0)
            self.assertFalse(summary["sh03_qualified"])
            self.assertEqual(events[-2:], ["stop", "close"])
            self.assertEqual(events.count("release"), 1 if calibrate else 4)


if __name__ == "__main__":
    unittest.main()
