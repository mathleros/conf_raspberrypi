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


def build_hardware_runtime(*, settings: RuntimeSettings | None = None) -> dict[str, Any]:
    """Construit les dépendances hardware réelles quand elles sont disponibles (Linux/Pi)."""
    runtime_settings = settings or load_runtime_settings()
    runtime: dict[str, Any] = {"robot": None, "camera": None, "sensor": None}

    try:
        if sys.platform.startswith("linux"):
            try:
                from irobot.hardware.sensors.hc_sr04 import HC_SR04
            except (ModuleNotFoundError, SystemExit) as exc:
                raise RuntimeError("Impossible de charger le pilote HC-SR04") from exc

            sensor = HC_SR04()
            runtime["sensor"] = sensor

            from irobot.hardware.smart_car.smart_car import SmartCar2WD
            from irobot.interfaces.robot_controller import RobotController

            car = SmartCar2WD(
                drive_speed=runtime_settings.drive_speed,
            )
            runtime["robot"] = RobotController(
                car,
                distance_sensor=sensor,
                obstacle_threshold_cm=runtime_settings.obstacle_threshold_cm,
            )

            from irobot.hardware.camera.camera_live_perception_pipeline import (
                CameraLivePerceptionPipeline,
            )

            runtime["camera"] = CameraLivePerceptionPipeline(sensor=sensor)
    except BaseException:
        logging.getLogger(__name__).exception("Impossible d'assembler le runtime hardware")
        try:
            close_hardware_runtime(runtime)
        except Exception:
            logging.getLogger(__name__).exception("Échec du nettoyage après une erreur d'assemblage")
        raise

    return runtime
