"""Live Raspberry Pi hardware assembly, kept separate from orchestration."""

from __future__ import annotations

import logging
import sys
from typing import Any

from irobot.config.settings import RuntimeSettings, load_runtime_settings


def _attempt_cleanup(errors: list[Exception], resource: Any, method: str, label: str) -> bool:
    try:
        callback = getattr(resource, method, None)
        if not callable(callback):
            return False
        callback()
    except Exception as exc:
        logging.getLogger(__name__).exception("Impossible de nettoyer %s", label)
        errors.append(exc)
        return True
    return True


def close_hardware_runtime(runtime: dict[str, Any]) -> None:
    """Arrête les moteurs et tente de libérer toutes les ressources matérielles."""
    errors: list[Exception] = []
    robot = runtime.get("robot")
    _attempt_cleanup(errors, robot, "stop", "le robot")
    _attempt_cleanup(errors, robot, "cleanup", "le robot")
    _attempt_cleanup(errors, runtime.get("sensor"), "cleanup", "le capteur")
    _attempt_cleanup(errors, runtime.get("camera"), "close", "la caméra")

    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise ExceptionGroup("Échecs pendant la fermeture du runtime hardware", errors)


def _build_sensor(runtime: dict[str, Any]) -> None:
    try:
        from irobot.hardware.sensors.hc_sr04 import HC_SR04
    except (ModuleNotFoundError, SystemExit) as exc:
        raise RuntimeError("Impossible de charger le pilote HC-SR04") from exc

    runtime["sensor"] = HC_SR04()


def _build_robot(runtime: dict[str, Any], settings: RuntimeSettings) -> None:
    from irobot.hardware.smart_car.smart_car import SmartCar2WD
    from irobot.interfaces.robot_controller import RobotController

    car = SmartCar2WD(
        drive_speed=settings.drive_speed,
    )
    runtime["robot"] = RobotController(
        car,
        distance_sensor=runtime["sensor"],
        obstacle_threshold_cm=settings.obstacle_threshold_cm,
    )


def _build_camera(runtime: dict[str, Any]) -> None:
    from irobot.hardware.camera.camera_live_pipeline import CameraLivePerceptionPipeline

    sensor = runtime["sensor"]
    distance_reader = sensor.read_distance_cm if sensor is not None else None
    runtime["camera"] = CameraLivePerceptionPipeline(distance_reader=distance_reader)


def build_hardware_runtime(*, settings: RuntimeSettings | None = None) -> dict[str, Any]:
    """Construit les dépendances hardware réelles quand elles sont disponibles (Linux/Pi)."""
    runtime_settings = settings or load_runtime_settings()
    runtime: dict[str, Any] = {"robot": None, "camera": None, "sensor": None}

    try:
        if sys.platform.startswith("linux"):
            _build_sensor(runtime)
            _build_robot(runtime, runtime_settings)
            _build_camera(runtime)
    except BaseException:
        logging.getLogger(__name__).exception("Impossible d'assembler le runtime hardware")
        try:
            close_hardware_runtime(runtime)
        except Exception:
            logging.getLogger(__name__).exception("Échec du nettoyage après une erreur d'assemblage")
        raise

    return runtime
