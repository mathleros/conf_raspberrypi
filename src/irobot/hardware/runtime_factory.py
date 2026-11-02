"""Live Raspberry Pi hardware assembly, kept separate from orchestration."""

from __future__ import annotations

import logging
import sys
from typing import Any

from irobot.config.settings import RuntimeSettings, load_runtime_settings


def build_hardware_runtime(*, settings: RuntimeSettings | None = None) -> dict[str, Any]:
    """Construit les dépendances hardware réelles quand elles sont disponibles (Linux/Pi)."""
    runtime_settings = settings or load_runtime_settings()
    if runtime_settings.protection_presence == "present":
        raise RuntimeError("Protection declared present: no qualified real P5 adapter; live assembly refused")
    runtime: dict[str, Any] = {
        "robot": None,
        "camera": None,
        "sensor": None,
    }

    if not sys.platform.startswith("linux"):
        return runtime

    try:
        from irobot.hardware.smart_car.smart_car import SmartCar2WD
        from irobot.interfaces.robot_controller import RobotController

        car = SmartCar2WD(drive_speed=runtime_settings.drive_speed, require_obstacle_sensor=False)
        runtime["robot"] = RobotController(car)
        runtime["sensor"] = car.distance_sensor
    except Exception:
        logging.getLogger(__name__).exception("Impossible d'initialiser le moteur et le capteur")
        runtime["robot"] = None
        runtime["sensor"] = None

    try:
        from irobot.hardware.camera.camera_live_pipeline import CameraLivePerceptionPipeline

        robot = runtime["robot"]
        distance_reader = robot.read_distance_cm if robot is not None and runtime["sensor"] is not None else None
        runtime["camera"] = CameraLivePerceptionPipeline(distance_reader=distance_reader)
    except Exception:
        logging.getLogger(__name__).exception("Impossible d'initialiser la perception camera")
        runtime["camera"] = None

    return runtime
