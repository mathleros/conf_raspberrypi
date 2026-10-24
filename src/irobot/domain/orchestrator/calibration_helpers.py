from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MotionCalibration:
    cm_per_second: float = 25.0
    deg_per_second: float = 180.0


def distance_to_duration_seconds(distance: float, unit: str, calibration: MotionCalibration) -> float:
    """Convert distance command to movement duration based on calibration profile."""
    if unit.lower() == "m":
        distance_cm = distance * 100.0
    else:
        distance_cm = distance
    distance_cm = max(0.0, float(distance_cm))
    return max(0.1, distance_cm / max(1e-6, calibration.cm_per_second))


def angle_to_duration_seconds(angle_deg: float, calibration: MotionCalibration) -> float:
    """Convert rotation angle command to movement duration based on calibration profile."""
    safe_angle = max(0.0, float(angle_deg))
    return max(0.1, safe_angle / max(1e-6, calibration.deg_per_second))
