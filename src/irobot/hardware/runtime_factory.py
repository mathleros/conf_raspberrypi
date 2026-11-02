"""Live Raspberry Pi hardware assembly, kept separate from orchestration."""

from __future__ import annotations

import logging
import sys
from typing import Any

from irobot.config.settings import RuntimeSettings, load_runtime_settings


def _build_robot(runtime: dict[str, Any], settings: RuntimeSettings) -> None:
    sensor = None
    car = None
    try:
        try:
            from irobot.hardware.sensors.hc_sr04 import HC_SR04
        except (ModuleNotFoundError, SystemExit) as exc:
            raise RuntimeError("Impossible de charger le pilote HC-SR04") from exc

        from irobot.hardware.smart_car.smart_car import SmartCar2WD
        from irobot.interfaces.robot_controller import RobotController

        sensor = HC_SR04()
        car = SmartCar2WD(
            distance_sensor=sensor,
            drive_speed=settings.drive_speed,
            require_obstacle_sensor=False,
        )
        runtime["robot"] = RobotController(car)
        runtime["sensor"] = sensor
    except Exception:
        logging.getLogger(__name__).exception("Impossible d'initialiser le moteur et le capteur")
        runtime["robot"] = None
        runtime["sensor"] = None
        try:
            if car is not None:
                car.cleanup()
            elif sensor is not None:
                sensor.cleanup()
        except Exception:
            logging.getLogger(__name__).exception("Impossible de libérer le capteur après l'échec de l'initialisation")


def _build_camera(runtime: dict[str, Any]) -> None:
    try:
        from irobot.hardware.camera.camera_live_pipeline import CameraLivePerceptionPipeline

        robot = runtime["robot"]
        distance_reader = robot.read_distance_cm if robot is not None and runtime["sensor"] is not None else None
        runtime["camera"] = CameraLivePerceptionPipeline(distance_reader=distance_reader)
    except Exception:
        logging.getLogger(__name__).exception("Impossible d'initialiser la perception camera")
        runtime["camera"] = None


def build_hardware_runtime(*, settings: RuntimeSettings | None = None) -> dict[str, Any]:
    """Construit les dépendances hardware réelles quand elles sont disponibles (Linux/Pi)."""
    runtime_settings = settings or load_runtime_settings()
    if runtime_settings.protection_presence == "present":
        raise RuntimeError("Protection declared present: no qualified real P5 adapter; live assembly refused")
    runtime: dict[str, Any] = {"robot": None, "camera": None, "sensor": None}

    if sys.platform.startswith("linux"):
        _build_robot(runtime, runtime_settings)
        _build_camera(runtime)

    return runtime
