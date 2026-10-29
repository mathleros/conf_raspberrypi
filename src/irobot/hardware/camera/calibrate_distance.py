"""Calibration de la distance caméra : affiche diameter_px et la distance estimée.

Usage :
    uv run calibrate-distance --color yellow
    uv run calibrate-distance --color yellow --known-distance-cm 100

Avec --known-distance-cm, place la balle à cette distance (mesurée) ; le script
moyenne plusieurs mesures et affiche le `focal_px` à reporter dans
config/runtime_calibration.toml, section [camera].
"""

from __future__ import annotations

import argparse
import statistics
import sys

import cv2

from irobot.config.settings import load_runtime_settings
from irobot.hardware.camera.color_detector import (
    CAMERA_INDEX,
    Picamera2,
    choose_best_result_with_metrics,
    detect_colored_objects,
)
from irobot.hardware.camera.distance_estimator import estimate_distance_cm, focal_from_known_distance


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    settings = load_runtime_settings()
    parser = argparse.ArgumentParser(description="Calibre l'estimation de distance de la balle.")
    parser.add_argument("--color", choices=["red", "yellow"], default="yellow")
    parser.add_argument("--ball-diameter-cm", type=float, default=settings.camera_ball_diameter_cm)
    parser.add_argument("--focal-px", type=float, default=settings.camera_focal_px)
    parser.add_argument("--known-distance-cm", type=float, default=None, help="distance réelle balle-caméra")
    parser.add_argument("--samples", type=int, default=30, help="mesures moyennées en mode --known-distance-cm")
    return parser.parse_args(argv)


def measure_diameter_px(frame_rgb, color: str) -> float | None:
    candidates = detect_colored_objects(frame_rgb, color_name=color, is_rgb=True)
    _, metrics = choose_best_result_with_metrics(candidates, color, frame_rgb.shape, robotic=True)
    if metrics is None or metrics["kind"] != "ball":
        return None
    return metrics["diameter_px"]


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if Picamera2 is None:
        sys.exit("Picamera2 indisponible : à lancer sur le Raspberry Pi.")

    camera = Picamera2(CAMERA_INDEX)
    # Picamera2 BGR888 fournit des octets R, G, B au détecteur is_rgb=True.
    camera.configure(camera.create_preview_configuration(main={"size": (640, 480), "format": "BGR888"}))
    camera.start()
    samples: list[float] = []
    try:
        while True:
            frame = cv2.rotate(camera.capture_array(), cv2.ROTATE_90_CLOCKWISE)
            diameter = measure_diameter_px(frame, args.color)
            if diameter is None:
                print("balle non détectée          ", end="\r", flush=True)
                continue

            if args.known_distance_cm is None:
                distance = estimate_distance_cm(diameter, args.ball_diameter_cm, args.focal_px)
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
            camera.stop()
        finally:
            camera.close()


if __name__ == "__main__":
    main()
