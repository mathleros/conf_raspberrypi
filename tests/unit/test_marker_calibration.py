from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from irobot.interfaces.marker_calibration import (
    ACQUISITION,
    SCHEMA,
    FrameLedger,
    main,
    parse_args,
    percentile95,
    read_checkerboard_traces,
    validate_calibration,
    write_record,
)


def calibration_document():
    return {
        "schema": SCHEMA, "type": "intrinsics", "acquisition": copy.deepcopy(ACQUISITION),
        "mounting": "fixture-A", "camera_matrix": [[600, 0, 240], [0, 600, 320], [0, 0, 1]],
        "distortion": [0, 0, 0, 0, 0], "training_rms_px": 0.1,
        "training_view_errors_px": [0.1], "holdout_view_errors_px": [0.2],
    }


class MarkerCalibrationTests(unittest.TestCase):
    def arguments(self):
        return [
            "record", "--output", "trace.jsonl", "--revision", "exact-archive-1",
            "--mounting", "fixture-A", "--condition", "inert target, face, daylight",
            "--calibration", "intrinsics.json", "--marker-cm", "8",
            "--authorized-camera", "--motors-isolated", "--zone-empty",
        ]

    def test_no_camera_confirmation_no_execution(self):
        for flag in ("--authorized-camera", "--motors-isolated", "--zone-empty"):
            with self.subTest(flag=flag), patch("sys.stderr", new=io.StringIO()):
                arguments = self.arguments()
                arguments.remove(flag)
                with self.assertRaises(SystemExit) as exc:
                    parse_args(arguments)
                self.assertEqual(exc.exception.code, 2)

    def test_nonfinite_inputs_and_unidentified_revision_rejected(self):
        for option, value in (
            ("--marker-cm", "nan"), ("--marker-cm", "inf"),
            ("--duration-s", "0"), ("--frames", "-1"), ("--revision", "HEAD"),
        ):
            with self.subTest(option=option, value=value), patch("sys.stderr", new=io.StringIO()):
                with self.assertRaises(SystemExit):
                    parse_args([*self.arguments(), option, value])

    def test_reference_requires_independent_uncertainty(self):
        with patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit):
            parse_args([*self.arguments(), "--reference-optical-cm", "150"])
        args = parse_args([
            *self.arguments(), "--reference-optical-cm", "150", "--reference-uncertainty-cm", "1",
        ])
        self.assertEqual(args.reference_optical_cm, 150)

    def test_distinct_timestamp_count_not_reads_or_state_transitions(self):
        ledger = FrameLedger()
        for timestamp, disposition in ((100, "valid"), (100, "valid"), (90, "valid"),
                                       (None, "valid"), (200, "absent"), (300, "ambiguous"),
                                       (400, "valid")):
            status = ledger.identify(timestamp)
            ledger.observe(status, disposition, 5)
        summary = ledger.summary(2, "frame_limit")
        self.assertEqual(summary["new_frames"], 4)
        self.assertEqual(summary["detected_fraction"], 0.5)
        self.assertEqual(summary["new_frames_per_s"], 2)
        self.assertEqual(summary["longest_nondetection_run"], 2)
        self.assertEqual(summary["counts"]["repeated_capture"], 1)
        self.assertEqual(summary["counts"]["out_of_order_capture"], 1)
        self.assertEqual(summary["counts"]["missing_sensor_timestamp"], 1)
        self.assertIsNone(summary["capture_to_result_p95_ms"])
        self.assertFalse(summary["sh03_qualified"])

    def test_missing_timestamp_is_not_a_new_frame(self):
        ledger = FrameLedger()
        for value in (True, 0, -1, "100", 1.0, None):
            self.assertEqual(ledger.identify(value), "missing_sensor_timestamp")
        self.assertEqual(ledger.new_frames, 0)
        summary = ledger.summary(0, "deadline")
        self.assertIsNone(summary["detected_fraction"])
        self.assertIsNone(summary["capture_return_to_result_p95_ms"])

    def test_nearest_rank_percentile_and_invalid_processing_time(self):
        self.assertEqual(percentile95(list(range(1, 101))), 95)
        ledger = FrameLedger()
        for duration in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                ledger.observe("new_capture", "valid", duration)

    def test_calibration_compatible_only_with_exact_geometry(self):
        data = calibration_document()
        self.assertIs(validate_calibration(data, "fixture-A"), data)
        with self.assertRaises(ValueError):
            validate_calibration(data, "fixture-B")
        for key, value in (("rotation", "none"), ("image_size", [640, 480]), ("format", "RGB888")):
            malformed = copy.deepcopy(data)
            malformed["acquisition"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_calibration(malformed, "fixture-A")

    def test_malformed_intrinsics_and_missing_errors_rejected(self):
        for key, value in (
            ("camera_matrix", [[1, 2], [3, 4]]), ("distortion", [0]),
            ("distortion", [0, 0, True, 0, 0]), ("distortion", [0, 0, float("nan"), 0, 0]),
            ("training_rms_px", float("inf")), ("holdout_view_errors_px", []),
            ("camera_matrix", [[0, 0, 240], [0, 600, 320], [0, 0, 1]]),
        ):
            data = calibration_document()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_calibration(data, "fixture-A")

    def test_jsonl_retains_negative_status_and_rejects_nan(self):
        stream = io.StringIO()
        write_record(stream, {"disposition": "absent", "robot_clearance_cm": None})
        self.assertEqual(json.loads(stream.getvalue())["disposition"], "absent")
        with self.assertRaises(ValueError):
            write_record(stream, {"distance": float("nan")})

    def test_cli_reports_missing_display_without_loading_hardware(self):
        with patch.dict("os.environ", {}, clear=True), patch("sys.stderr", new=io.StringIO()) as errors:
            self.assertEqual(main(self.arguments()), 2)
        self.assertIn("DISPLAY absent", errors.getvalue())

    def test_offline_trace_selection_rejects_duplicates_and_incompatible_mounting(self):
        args = parse_args([
            "solve", "--output", "calibration.json", "--traces", "view.jsonl",
            "--revision", "exact-archive-1", "--mounting", "fixture-A",
            "--columns", "3", "--rows", "3", "--square-cm", "2",
        ])
        header = {
            "type": "run", "schema": SCHEMA, "mode": "calibrate", "acquisition": ACQUISITION,
            "mounting": args.mounting, "revision": args.revision,
            "parameters": {"columns": 3, "rows": 3, "square_cm": 2},
        }
        row = {
            "type": "frame", "selected_for_calibration": True, "sensor_timestamp_ns": 100,
            "capture_status": "new_capture", "disposition": "valid",
            "corners_px": [[10 + x * 10, 20 + y * 10] for y in range(3) for x in range(3)],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "view.jsonl"
            with path.open("x") as stream:
                for record in (header, row, {"type": "summary", "termination": "operator_stop"}):
                    write_record(stream, record)
            args.traces = [path]
            self.assertEqual(read_checkerboard_traces(args), [row["corners_px"]])
            args.mounting = "other"
            with self.assertRaises(ValueError):
                read_checkerboard_traces(args)
            args.mounting = header["mounting"]
            args.traces = [path, path]
            with self.assertRaises(ValueError):
                read_checkerboard_traces(args)
            copied = Path(directory) / "copied.jsonl"
            copied.write_bytes(path.read_bytes())
            args.traces = [path, copied]
            with self.assertRaises(ValueError):
                read_checkerboard_traces(args)


if __name__ == "__main__":
    unittest.main()
