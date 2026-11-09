"""Capteur ultrason HC-SR04 sur Raspberry Pi.

Le capteur marche via deux GPIO :
- TRIG : émission d'une impulsion ultrasonore
- ECHO : détection du signal de retour

Le test du projet consiste à mesurer la distance du premier objet situé devant le
capteur.
"""

from __future__ import annotations

import argparse
import math
import threading
import time
from collections.abc import Callable

try:
    from gpiozero import DigitalInputDevice, DigitalOutputDevice
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "Ce script nécessite gpiozero sur Raspberry Pi. "
        "Installez le support GPIO puis relancez le programme.",
    ) from exc


class HC_SR04:
    """Mesure la distance à l'objet le plus proche devant le capteur."""

    CACHE_TTL_S = 0.06

    def __init__(
        self,
        trigger_pin: int = 17,
        echo_pin: int = 27,
        max_distance_cm: float = 400.0,
        *,
        time_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.trigger = DigitalOutputDevice(trigger_pin)
        self.echo = DigitalInputDevice(echo_pin, pull_up=False)
        self.max_distance_cm = max_distance_cm
        self._time_fn = time_fn
        self._sleep_fn = sleep_fn
        self._read_lock = threading.Lock()
        self._last_distance_cm: float | None = None
        self._last_distance_at: float | None = None
        self._closed = False

    def _trigger_pulse(self) -> None:
        self.trigger.on()
        self._sleep_fn(0.00001)
        self.trigger.off()

    def _wait_for_level(self, expected: int, timeout_s: float = 0.05) -> bool:
        deadline = self._time_fn() + timeout_s
        while self._time_fn() < deadline:
            if self.echo.value == expected:
                return True
            self._sleep_fn(0.00001)
        return False

    def read_distance_cm(self) -> float | None:
        """Retourne une mesure récente en cache, sinon mesure la distance en cm."""
        with self._read_lock:
            now = self._time_fn()
            if (
                self._last_distance_cm is not None
                and self._last_distance_at is not None
                and 0.0 <= now - self._last_distance_at < self.CACHE_TTL_S
            ):
                return self._last_distance_cm

            self._last_distance_cm = None
            self._last_distance_at = None
            self._trigger_pulse()
            if not self._wait_for_level(1):
                return None

            start = self._time_fn()
            if not self._wait_for_level(0):
                return None

            elapsed = self._time_fn() - start
            if elapsed <= 0:
                return None

            distance_cm = (elapsed * 34300.0) / 2.0
            if distance_cm > self.max_distance_cm:
                # Écho trop long : rien devant le capteur, ce n'est pas une panne.
                return math.inf

            self._last_distance_cm = distance_cm
            self._last_distance_at = self._time_fn()
            return distance_cm

    def cleanup(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.trigger.close()
        finally:
            self.echo.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mesure la distance du premier objet détecté par un HC-SR04.",
    )
    parser.add_argument(
        "--trigger-pin",
        type=int,
        default=17,
        help="GPIO BCM du signal TRIG.",
    )
    parser.add_argument(
        "--echo-pin",
        type=int,
        default=27,
        help="GPIO BCM du signal ECHO.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Intervalle entre deux mesures, en secondes.",
    )
    parser.add_argument(
        "--max-distance",
        type=float,
        default=400.0,
        help="Distance maximale mesurable, en cm.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Mesure une seule valeur puis quitte.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    sensor = HC_SR04(
        trigger_pin=args.trigger_pin,
        echo_pin=args.echo_pin,
        max_distance_cm=args.max_distance,
    )

    try:
        print(f"Mesure HC-SR04 via TRIG={args.trigger_pin} / ECHO={args.echo_pin}")
        print("Objectif : afficher la distance du premier objet devant le capteur.")

        while True:
            distance = sensor.read_distance_cm()
            if distance is None:
                print("Mesure invalide : capteur sans réponse.")
            elif math.isinf(distance):
                print("Aucun objet détecté dans la plage mesurée.")
            else:
                print(f"Distance détectée : {distance:.2f} cm")

            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nInterruption clavier : arrêt du capteur.")
    finally:
        sensor.cleanup()
        if args.once:
            print("Fermeture propre du capteur...")

if __name__ == "__main__":
    main()
