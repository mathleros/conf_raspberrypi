"""Outil de calibration caméra : affiche diameter_px et la distance estimée.

Usage :
    uv run calibrate-distance --color yellow
    uv run calibrate-distance --color yellow --known-distance-cm 100

Avec --known-distance-cm, place la balle à cette distance (mesurée) ; le script
moyenne plusieurs mesures et affiche le `focal_px` à reporter dans
src/irobot/config/runtime_settings.toml, section [camera].
"""

from __future__ import annotations

import argparse
import statistics
import sys

import cv2

from irobot.app.config.settings import load_runtime_settings
from irobot.app.hardware.camera.detector import ColorDetector
from irobot.app.hardware.camera.frame_enhancer import (
    FrameEnhancer,
    configure_exposure,
)

try:
    from picamera2 import Picamera2
except ModuleNotFoundError:  # pragma: no cover - environnements hors Raspberry Pi
    Picamera2 = None

CAMERA_INDEX = 0


def focal_from_known_distance(diameter_px: float, ball_diameter_cm: float, known_distance_cm: float) -> float | None:
    """Inverse du modèle : focal_px = diameter_px * known_distance_cm / ball_diameter_cm."""
    if diameter_px is None or diameter_px <= 0 or ball_diameter_cm <= 0 or known_distance_cm <= 0:
        return None
    return diameter_px * known_distance_cm / ball_diameter_cm


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    settings = load_runtime_settings()
    parser = argparse.ArgumentParser(description="Calibre l'estimation de distance de la balle.")
    parser.add_argument("--color", choices=["red", "yellow"], default="yellow")
    parser.add_argument("--ball-diameter-cm", type=float, default=settings.camera_ball_diameter_cm)
    parser.add_argument("--focal-px", type=float, default=settings.camera_focal_px)
    parser.add_argument("--known-distance-cm", type=float, default=None, help="distance réelle balle-caméra")
    parser.add_argument("--samples", type=int, default=30, help="mesures moyennées en mode --known-distance-cm")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if Picamera2 is None:
        sys.exit("Picamera2 indisponible : à lancer sur le Raspberry Pi.")

    settings = load_runtime_settings()
    enhancer = FrameEnhancer(settings)
    detector = ColorDetector(args.color, args.ball_diameter_cm, args.focal_px)
    camera = Picamera2(CAMERA_INDEX)
    started = False
    samples: list[float] = []
    try:
        # Picamera2 BGR888 fournit des octets R, G, B au détecteur is_rgb=True.
        camera.configure(camera.create_preview_configuration(
            main={"size": settings.camera_capture_size_px, "format": "BGR888"},
        ))
        configure_exposure(camera, settings)
        camera.start()
        started = True
        while True:
            frame = cv2.rotate(camera.capture_array(), cv2.ROTATE_180)
            frame = enhancer.apply(frame)
            detection = detector.detect(frame)
            if detection is None or not detection.label.endswith("_ball"):
                print("balle non détectée          ", end="\r", flush=True)
                continue
            diameter = detection.diameter_px
            if diameter is None:
                print("diamètre de balle indisponible          ", end="\r", flush=True)
                continue

            if args.known_distance_cm is None:
                distance = detection.distance_cm
                if distance is None:
                    print("distance indisponible          ", end="\r", flush=True)
                    continue
                print(f"diameter_px={diameter:7.1f}  distance={distance:7.1f} cm", end="\r", flush=True)
                continue

            samples.append(diameter)
            if len(samples) >= max(1, args.samples):
                median = statistics.median(samples)
                focal = focal_from_known_distance(median, args.ball_diameter_cm, args.known_distance_cm)
                print(f"\ndiameter_px (médiane) = {median:.1f}")
                print(f"À reporter dans [camera] : focal_px = {focal:.1f}")
                return
    except KeyboardInterrupt:
        print()
    finally:
        try:
            if started:
                camera.stop()
        finally:
            camera.close()


if __name__ == "__main__":
    main()
