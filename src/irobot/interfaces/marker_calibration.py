"""Offline-testable SH-03 tooling; live acquisition is explicitly opt-in."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from typing import TextIO

from irobot.interfaces.human_perception import (
    ObservationDisposition,
    OpenCVArucoMarkerDecoder,
)
from irobot.interfaces.marker_diagnostic import (
    EXPECTED_CAMERA_MODEL,
    TEST_MARKER_IDENTITY,
)


SCHEMA = "sh03-optics-v1"
ACQUISITION = {
    "model": EXPECTED_CAMERA_MODEL,
    "camera_index": 0,
    "size_before_rotation": [640, 480],
    "format": "BGR888",
    "rotation": "90_clockwise",
    "image_size": [480, 640],
}


def positive(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Expected a finite positive number")
    return number


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Expected a positive integer")
    return number


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    for mode in ("calibrate", "record"):
        command = commands.add_parser(mode)
        command.add_argument("--output", type=Path, required=True, help="New JSONL file, never overwritten")
        command.add_argument("--revision", required=True, help="Exact Pi commit/archive identifier")
        command.add_argument("--mounting", required=True, help="Mounting identifier and measured geometry")
        command.add_argument("--duration-s", type=positive, default=120 if mode == "calibrate" else 30)
        command.add_argument("--authorized-camera", action="store_true")
        command.add_argument("--motors-isolated", action="store_true")
        command.add_argument("--zone-empty", action="store_true")
    calibration = commands.choices["calibrate"]
    calibration.add_argument("--columns", type=positive_int, required=True, help="Internal checkerboard corners")
    calibration.add_argument("--rows", type=positive_int, required=True, help="Internal checkerboard corners")
    calibration.add_argument("--square-cm", type=positive, required=True, help="Measured checkerboard square side")
    calibration.add_argument("--samples", type=positive_int, default=20)
    calibration.add_argument("--interval-s", type=positive, default=1)
    calibration.add_argument("--calibration-output", type=Path, required=True)
    solve = commands.add_parser("solve", help="Combine checkerboard traces offline; no camera")
    solve.add_argument("--output", type=Path, required=True)
    solve.add_argument("--traces", type=Path, nargs="+", required=True)
    solve.add_argument("--revision", required=True)
    solve.add_argument("--mounting", required=True)
    solve.add_argument("--columns", type=positive_int, required=True)
    solve.add_argument("--rows", type=positive_int, required=True)
    solve.add_argument("--square-cm", type=positive, required=True)
    record = commands.choices["record"]
    record.add_argument("--calibration", type=Path, required=True)
    record.add_argument("--marker-cm", type=positive, required=True)
    record.add_argument("--condition", required=True, help="Distance, height, angles, offset, light and negative case")
    record.add_argument("--frames", type=positive_int, default=100)
    record.add_argument("--reference-optical-cm", type=positive)
    record.add_argument("--reference-uncertainty-cm", type=positive)
    args = parser.parse_args(argv)
    if args.mode != "solve" and not all((args.authorized_camera, args.motors_isolated, args.zone_empty)):
        parser.error("Camera authorization, isolated motors and empty zone must all be explicitly confirmed")
    if not args.revision.strip() or args.revision.strip().upper() == "HEAD" or not args.mounting.strip():
        parser.error("An exact revision and explicit mounting description are required")
    if args.mode in ("calibrate", "solve"):
        if min(args.columns, args.rows) < 3 or (args.mode == "calibrate" and args.samples < 12):
            parser.error("Use at least 3x3 internal corners and 12 views (collection floor, not qualification)")
        if args.mode == "calibrate" and args.output.resolve() == args.calibration_output.resolve():
            parser.error("Trace and calibration files must differ")
    elif (args.reference_optical_cm is None) != (args.reference_uncertainty_cm is None):
        parser.error("Optical reference and its uncertainty must be supplied together")
    return args


def write_record(stream: TextIO, record: dict) -> None:
    stream.write(json.dumps(record, allow_nan=False, ensure_ascii=True) + "\n")
    stream.flush()


def percentile95(values: list[float]) -> float | None:
    if not values:
        return None
    return sorted(values)[math.ceil(0.95 * len(values)) - 1]


class FrameLedger:
    """Sensor timestamps identify captures, not an assumed latency clock."""

    def __init__(self) -> None:
        self.last_sensor_ns: int | None = None
        self.counts: Counter[str] = Counter()
        self.new_frames = 0
        self.detected_frames = 0
        self.current_loss = 0
        self.max_loss = 0
        self.processing_ms: list[float] = []

    def identify(self, sensor_ns: object) -> str:
        if type(sensor_ns) is not int or sensor_ns <= 0:
            return "missing_sensor_timestamp"
        if self.last_sensor_ns is not None:
            if sensor_ns == self.last_sensor_ns:
                return "repeated_capture"
            if sensor_ns < self.last_sensor_ns:
                return "out_of_order_capture"
        self.last_sensor_ns = sensor_ns
        self.new_frames += 1
        return "new_capture"

    def observe(self, capture_status: str, disposition: str, processing_ms: float) -> None:
        if not math.isfinite(processing_ms) or processing_ms < 0:
            raise ValueError("Invalid processing duration")
        self.counts[capture_status] += 1
        if capture_status != "new_capture":
            return
        self.counts[disposition] += 1
        self.processing_ms.append(processing_ms)
        if disposition == "valid":
            self.detected_frames += 1
            self.current_loss = 0
        else:
            self.current_loss += 1
            self.max_loss = max(self.max_loss, self.current_loss)

    def summary(self, elapsed: float, termination: str) -> dict:
        return {
            "type": "summary",
            "termination": termination,
            "new_frames": self.new_frames,
            "counts": dict(self.counts),
            "detected_fraction": self.detected_frames / self.new_frames if self.new_frames else None,
            "new_frames_per_s": self.new_frames / elapsed if elapsed > 0 else None,
            "longest_nondetection_run": self.max_loss,
            "capture_return_to_result_p95_ms": percentile95(self.processing_ms),
            "capture_to_result_p95_ms": None,
            "sh03_qualified": False,
            "limitations": [
                "Detector validity is not calibrated human-observation acceptance",
                "SensorTimestamp clock correspondence/freshness is not qualified",
                "Processing after capture return excludes sensor/pipeline/wait latency",
                "No robot-to-person clearance model or quality thresholds are qualified",
            ],
        }


def validate_calibration(data: object, mounting: str) -> dict:
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("type") != "intrinsics":
        raise ValueError("Unsupported calibration document")
    if data.get("acquisition") != ACQUISITION or data.get("mounting") != mounting:
        raise ValueError("Calibration acquisition/mounting mismatch; recalibration required")
    matrix = data.get("camera_matrix")
    distortion = data.get("distortion")
    if (not isinstance(matrix, list) or len(matrix) != 3
            or any(not isinstance(row, list) or len(row) != 3 for row in matrix)
            or not isinstance(distortion, list) or len(distortion) != 5):
        raise ValueError("Expected a 3x3 matrix and five OpenCV distortion coefficients")
    values = [value for row in matrix for value in row] + distortion
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        raise ValueError("Calibration coefficients must be finite numbers")
    if (matrix[0][0] <= 0 or matrix[1][1] <= 0 or matrix[2] != [0, 0, 1]
            or matrix[0][1] != 0 or matrix[1][0] != 0):
        raise ValueError("Invalid pinhole camera matrix")
    errors = [data.get("training_rms_px")]
    for key in ("training_view_errors_px", "holdout_view_errors_px"):
        entries = data.get(key)
        if not isinstance(entries, list) or not entries:
            raise ValueError("Calibration reprojection errors must be retained")
        errors.extend(entries)
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in errors):
        raise ValueError("Invalid calibration reprojection errors")
    return data


def calibrate_views(image_points: list, args: argparse.Namespace, cv2, np) -> dict:
    if len(image_points) < 12:
        raise ValueError("Insufficient distinct checkerboard views; no calibration produced")
    board = np.zeros((args.rows * args.columns, 3), np.float32)
    board[:, :2] = np.mgrid[0:args.columns, 0:args.rows].T.reshape(-1, 2) * args.square_cm
    holdout_count = max(2, len(image_points) // 5)
    training = image_points[:-holdout_count]
    rms, matrix, distortion, rotations, translations = cv2.calibrateCamera(
        [board.copy() for _ in training], training, tuple(ACQUISITION["image_size"]), None, None,
    )
    training_errors = []
    for points, rotation, translation in zip(training, rotations, translations):
        projected, _ = cv2.projectPoints(board, rotation, translation, matrix, distortion)
        training_errors.append(float(np.sqrt(np.mean((projected - points) ** 2) * 2)))
    holdout_errors = []
    for points in image_points[-holdout_count:]:
        solved, rotation, translation = cv2.solvePnP(board, points, matrix, distortion)
        if not solved:
            raise ValueError("Holdout pose solve failed; no calibration produced")
        projected, _ = cv2.projectPoints(board, rotation, translation, matrix, distortion)
        holdout_errors.append(float(np.sqrt(np.mean((projected - points) ** 2) * 2)))
    data = {
        "schema": SCHEMA,
        "type": "intrinsics",
        "acquisition": ACQUISITION,
        "mounting": args.mounting,
        "revision": args.revision,
        "opencv_version": cv2.__version__,
        "board": {"columns": args.columns, "rows": args.rows, "square_cm": args.square_cm},
        "camera_matrix": matrix.tolist(),
        "distortion": distortion.reshape(-1).tolist(),
        "training_rms_px": float(rms),
        "training_view_errors_px": training_errors,
        "holdout_view_errors_px": holdout_errors,
        "sh03_qualified": False,
    }
    validate_calibration(data, args.mounting)
    json.dumps(data, allow_nan=False)
    return data


def read_checkerboard_traces(args: argparse.Namespace) -> list[list[list[float]]]:
    views = []
    digests = set()
    paths = [path.resolve() for path in args.traces]
    if len(set(paths)) != len(paths):
        raise ValueError("Duplicate trace paths would count the same captures twice")
    for path in paths:
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest in digests:
            raise ValueError("Copied traces would count the same captures twice")
        digests.add(digest)
        records = [json.loads(line) for line in content.decode("utf-8").splitlines() if line.strip()]
        if not records or not all(isinstance(row, dict) for row in records):
            raise ValueError(f"Malformed trace: {path}")
        header, summary = records[0], records[-1]
        if (header.get("type") != "run" or header.get("schema") != SCHEMA
                or header.get("mode") != "calibrate" or header.get("acquisition") != ACQUISITION
                or header.get("mounting") != args.mounting or header.get("revision") != args.revision
                or summary.get("type") != "summary"
                or summary.get("termination") not in ("deadline", "operator_stop", "interrupted", "view_limit")):
            raise ValueError(f"Incompatible or failed checkerboard trace: {path}")
        parameters = header.get("parameters")
        if not isinstance(parameters, dict) or any(
            parameters.get(key) != getattr(args, key) for key in ("rows", "columns", "square_cm")
        ):
            raise ValueError(f"Checkerboard dimensions differ: {path}")
        seen = set()
        for row in records[1:-1]:
            if row.get("selected_for_calibration") is not True:
                continue
            timestamp = row.get("sensor_timestamp_ns")
            points = row.get("corners_px")
            if (row.get("capture_status") != "new_capture" or row.get("disposition") != "valid"
                    or type(timestamp) is not int or timestamp <= 0 or timestamp in seen
                    or not isinstance(points, list) or len(points) != args.rows * args.columns):
                raise ValueError(f"Invalid selected checkerboard capture: {path}")
            seen.add(timestamp)
            for point in points:
                if (not isinstance(point, list) or len(point) != 2
                        or any(type(value) not in (int, float) or not math.isfinite(value) for value in point)
                        or not 0 <= point[0] < 480 or not 0 <= point[1] < 640):
                    raise ValueError(f"Invalid checkerboard corners: {path}")
            views.append(points)
    return views


def solve_offline(args: argparse.Namespace) -> int:
    views = read_checkerboard_traces(args)
    if len(views) < 12:
        raise ValueError("At least 12 selected views are required; no camera will be opened")
    import cv2
    import numpy as np

    try:
        data = calibrate_views(
            [np.array(points, dtype=np.float32).reshape(-1, 1, 2) for points in views], args, cv2, np,
        )
    except cv2.error as exc:
        raise RuntimeError(f"OpenCV offline calibration failed: {exc}") from exc
    data["source_traces"] = [
        {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in args.traces
    ]
    with args.output.open("x", encoding="utf-8") as output:
        write_record(output, data)
    print("Candidate intrinsics saved; SH-03 remains unqualified.", flush=True)
    return 0


def marker_poses(corners, marker_cm: float, calibration: dict, cv2, np) -> list[dict]:
    half = marker_cm / 2
    square = np.array(
        [(-half, half, 0), (half, half, 0), (half, -half, 0), (-half, -half, 0)],
        dtype=np.float64,
    )
    matrix = np.array(calibration["camera_matrix"], dtype=np.float64)
    distortion = np.array(calibration["distortion"], dtype=np.float64)
    points = np.array(corners, dtype=np.float64).reshape(4, 1, 2)
    count, rotations, translations, _ = cv2.solvePnPGeneric(
        square, points, matrix, distortion, flags=cv2.SOLVEPNP_IPPE_SQUARE,
    )
    candidates = []
    if not count:
        return candidates
    for rotation, translation in zip(rotations, translations):
        rotation_matrix, _ = cv2.Rodrigues(rotation)
        transformed = (rotation_matrix @ square.T + translation.reshape(3, 1)).T
        if not np.isfinite(transformed).all() or (transformed[:, 2] <= 0).any():
            continue
        projected, _ = cv2.projectPoints(square, rotation, translation, matrix, distortion)
        candidates.append({
            "translation_cm": translation.reshape(-1).tolist(),
            "rotation_vector_rad": rotation.reshape(-1).tolist(),
            "optical_range_cm": float(np.linalg.norm(translation)),
            "optical_depth_cm": float(translation.reshape(-1)[2]),
            "reprojection_rms_px": float(np.sqrt(np.mean((projected - points) ** 2) * 2)),
        })
    json.dumps(candidates, allow_nan=False)
    return candidates


def run_live(args: argparse.Namespace) -> int:
    import os
    from importlib.metadata import version

    if not os.environ.get("DISPLAY"):
        raise ValueError("DISPLAY absent; camera will not be opened")
    calibration = None
    calibration_hash = None
    if args.mode == "record":
        content = args.calibration.read_bytes()
        calibration = validate_calibration(json.loads(content), args.mounting)
        calibration_hash = hashlib.sha256(content).hexdigest()
    import cv2
    import numpy as np
    from picamera2 import Picamera2

    camera_info = Picamera2.global_camera_info()
    if not camera_info or str(camera_info[0].get("Model", "")).lower() != EXPECTED_CAMERA_MODEL:
        raise ValueError("Camera 0 is not reported OV5647; no camera opened")
    decoder = OpenCVArucoMarkerDecoder(TEST_MARKER_IDENTITY) if args.mode == "record" else None
    ledger = FrameLedger()
    views = []
    last_view = None
    last_view_time = -math.inf
    termination = "error"
    started_at = time.monotonic()
    with ExitStack() as stack:
        trace = stack.enter_context(args.output.open("x", encoding="utf-8"))
        calibration_file = (
            stack.enter_context(args.calibration_output.open("x", encoding="utf-8"))
            if args.mode == "calibrate" else None
        )
        write_record(trace, {
            "type": "run", "schema": SCHEMA,
            "utc": datetime.now(timezone.utc).isoformat(),
            "mode": args.mode, "acquisition": ACQUISITION, "camera_info": camera_info,
            "revision": args.revision, "mounting": args.mounting,
            "opencv_version": cv2.__version__, "picamera2_version": version("picamera2"),
            "parameters": {key: str(value) if isinstance(value, Path) else value
                           for key, value in vars(args).items()},
            "calibration_sha256": calibration_hash,
            "images_saved": False, "sh03_qualified": False,
        })
        camera = Picamera2(0)
        stack.callback(camera.close)
        stack.callback(cv2.destroyAllWindows)
        try:
            config = camera.create_preview_configuration(
                main={"size": (640, 480), "format": "BGR888"},
                buffer_count=2, queue=False,
            )
            camera.configure(config)
            effective = camera.camera_configuration()
            if (tuple(effective["main"]["size"]) != (640, 480)
                    or effective["main"]["format"] != "BGR888"):
                raise ValueError("Effective camera configuration differs from requested acquisition")
            transform = effective["transform"]
            if any(getattr(transform, name) for name in ("hflip", "vflip", "transpose")):
                raise ValueError("Unexpected hardware image transform; camera will not be started")
            write_record(trace, {
                "type": "camera_configuration",
                "main": {"size": list(effective["main"]["size"]), "format": effective["main"]["format"]},
                "transform": str(effective["transform"]),
            })
            camera.start()
            stack.callback(camera.stop)
            started_at = time.monotonic()
            while time.monotonic() - started_at < args.duration_s:
                request = camera.capture_request()
                returned = time.monotonic()
                try:
                    metadata = request.get_metadata()
                    rgb = request.make_array("main")
                finally:
                    request.release()
                frame = cv2.rotate(rgb, cv2.ROTATE_90_CLOCKWISE)
                if [frame.shape[1], frame.shape[0]] != ACQUISITION["image_size"]:
                    raise ValueError("Actual image dimensions differ from calibration")
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                sensor_ns = metadata.get("SensorTimestamp")
                capture_status = ledger.identify(sensor_ns)
                row = {
                    "type": "frame", "sensor_timestamp_ns": sensor_ns,
                    "capture_status": capture_status, "capture_return_monotonic_s": returned,
                    "exposure_us": metadata.get("ExposureTime"), "analogue_gain": metadata.get("AnalogueGain"),
                }
                if args.mode == "calibrate":
                    found, corners = cv2.findChessboardCornersSB(gray, (args.columns, args.rows))
                    disposition = "valid" if found else "absent"
                    selected = False
                    if found:
                        corners = np.asarray(corners, dtype=np.float32)
                        changed = last_view is None or float(np.max(np.abs(corners - last_view))) > 2
                        if capture_status == "new_capture" and changed and returned - last_view_time >= args.interval_s:
                            views.append(corners.copy())
                            last_view = corners.copy()
                            last_view_time = returned
                            selected = True
                        row["corners_px"] = corners.reshape(-1, 2).tolist()
                        cv2.drawChessboardCorners(frame, (args.columns, args.rows), corners, found)
                    row.update({"selected_for_calibration": selected, "selected_views": len(views)})
                else:
                    detection = decoder.detect(gray)
                    disposition = detection.disposition.value
                    row.update({
                        "reason": detection.reason, "corners_px": detection.corners_px,
                        "robot_clearance_cm": None, "pose_candidates": [],
                        "pose_status": "not_detected",
                    })
                    if detection.disposition is ObservationDisposition.VALID:
                        poses = marker_poses(detection.corners_px, args.marker_cm, calibration, cv2, np)
                        for pose in poses:
                            pose["optical_reference_error_cm"] = (
                                pose["optical_range_cm"] - args.reference_optical_cm
                                if args.reference_optical_cm is not None else None
                            )
                        row["pose_candidates"] = poses
                        row["pose_status"] = "ambiguous" if len(poses) > 1 else "candidate" if poses else "failed"
                observed = time.monotonic()
                duration_ms = (observed - returned) * 1000
                ledger.observe(capture_status, disposition, duration_ms)
                row.update({"disposition": disposition, "result_monotonic_s": observed,
                            "capture_return_to_result_ms": duration_ms})
                write_record(trace, row)
                cv2.putText(frame, f"{args.mode}: {ledger.new_frames} new; {disposition}",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                cv2.imshow("SH-03 optics (q: stop)", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    termination = "operator_stop"
                    break
                if args.mode == "record" and ledger.new_frames >= args.frames:
                    termination = "frame_limit"
                    break
                if args.mode == "calibrate" and len(views) >= args.samples:
                    termination = "view_limit"
                    break
            else:
                termination = "deadline"
            if args.mode == "calibrate":
                if termination != "view_limit":
                    print("Calibration incomplete: requested views not collected.", file=sys.stderr)
                    return 2
                termination = "calibration_error"
                data = calibrate_views(views, args, cv2, np)
                write_record(calibration_file, data)
                termination = "view_limit"
            elif termination != "frame_limit":
                print("Record incomplete: requested new captures not collected.", file=sys.stderr)
                return 2
            return 0
        except KeyboardInterrupt:
            termination = "interrupted"
            print("Acquisition interrupted; partial records retained.", file=sys.stderr)
            return 130
        except cv2.error as exc:
            termination = "opencv_error"
            raise RuntimeError(f"OpenCV failed: {exc}") from exc
        finally:
            summary = ledger.summary(time.monotonic() - started_at, termination)
            write_record(trace, summary)
            print(json.dumps(summary, allow_nan=False), flush=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return solve_offline(args) if args.mode == "solve" else run_live(args)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f"SH-03 tooling failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
