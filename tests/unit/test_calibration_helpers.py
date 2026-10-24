from __future__ import annotations

from irobot.domain.orchestrator.calibration_helpers import (
    MotionCalibration,
    angle_to_duration_seconds,
    distance_to_duration_seconds,
)


def test_distance_to_duration_seconds_cm():
    calibration = MotionCalibration(cm_per_second=20.0, deg_per_second=180.0)
    assert distance_to_duration_seconds(40.0, "cm", calibration) == 2.0


def test_distance_to_duration_seconds_meters():
    calibration = MotionCalibration(cm_per_second=25.0, deg_per_second=180.0)
    assert distance_to_duration_seconds(0.5, "m", calibration) == 2.0


def test_angle_to_duration_seconds():
    calibration = MotionCalibration(cm_per_second=25.0, deg_per_second=90.0)
    assert angle_to_duration_seconds(180.0, calibration) == 2.0
