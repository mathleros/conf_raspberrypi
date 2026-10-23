#!/usr/bin/env python3
import argparse
import sys
import time

try:
    from gpiozero import DigitalInputDevice, DigitalOutputDevice
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Le module gpiozero n'est pas installé. "
        "Exécute d'abord : sudo ./scripts/install_rpigpio.sh"
    ) from exc

BAR_WIDTH = 32
FULL_BLOCK = "█"
EMPTY_BLOCK = "░"


def wait_for_level(echo, expected_level: int, timeout_s: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if echo.value == expected_level:
            return True
        time.sleep(0.00001)
    return False


def measure_distance(trigger, echo, max_distance_cm: float = 200.0) -> float | None:
    """Mesure la distance du premier objet devant le capteur."""
    trigger.on()
    time.sleep(0.00001)
    trigger.off()

    if not wait_for_level(echo, 1, timeout_s=0.05):
        return None
    echo_start = time.monotonic()

    if not wait_for_level(echo, 0, timeout_s=0.05):
        return None
    echo_end = time.monotonic()

    elapsed = echo_end - echo_start
    if elapsed <= 0:
        return None

    distance_cm = (elapsed * 34300.0) / 2.0
    if distance_cm > max_distance_cm:
        return None
    return distance_cm


def meter(value_cm: float, min_cm: float = 0.0, max_cm: float = 200.0) -> str:
    if value_cm <= min_cm:
        return EMPTY_BLOCK * BAR_WIDTH
    if value_cm >= max_cm:
        return FULL_BLOCK * BAR_WIDTH

    ratio = (value_cm - min_cm) / (max_cm - min_cm)
    filled = int(round(ratio * BAR_WIDTH))
    filled = max(0, min(BAR_WIDTH, filled))
    return FULL_BLOCK * filled + EMPTY_BLOCK * (BAR_WIDTH - filled)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test du capteur HC-SR04 : affiche la distance du premier objet détecté."
    )
    parser.add_argument("--trigger-pin", type=int, default=17, help="GPIO BCM du signal TRIG.")
    parser.add_argument("--echo-pin", type=int, default=27, help="GPIO BCM du signal ECHO.")
    parser.add_argument("--duration", type=float, default=5.0, help="Durée de mesure totale en secondes.")
    parser.add_argument("--interval", type=float, default=0.1, help="Intervalle entre deux mesures en secondes.")
    parser.add_argument("--max-distance", type=float, default=200.0, help="Distance maximale en cm avant retour None.")
    args = parser.parse_args()

    trigger = DigitalOutputDevice(args.trigger_pin)
    echo = DigitalInputDevice(args.echo_pin, pull_up=False, pull_down=False)

    print(f"Capteur HC-SR04 — TRIG={args.trigger_pin}, ECHO={args.echo_pin}")
    print("Mesure la distance du premier objet devant le capteur.")
    print(f"Durée du test : {args.duration:.1f}s")

    distances = []
    start = time.monotonic()

    try:
        while time.monotonic() - start < args.duration:
            distance = measure_distance(trigger, echo, max_distance_cm=args.max_distance)
            if distance is None:
                line = f"Aucun objet détecté dans la plage ({args.max_distance:.0f} cm)"
            else:
                distances.append(distance)
                line = f"Distance : {distance:5.2f} cm  {meter(distance, 0.0, args.max_distance)}"
            sys.stdout.write("\r" + line)
            sys.stdout.flush()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nInterruption clavier : arrêt du test distance.")
    finally:
        trigger.close()
        echo.close()

    print()
    if distances:
        avg = sum(distances) / len(distances)
        print(f"Mesures : {len(distances)}")
        print(f"Distance min : {min(distances):.2f} cm")
        print(f"Distance max : {max(distances):.2f} cm")
        print(f"Distance moyenne : {avg:.2f} cm")
    else:
        print("Aucune distance n'a été mesurée durant le test.")


if __name__ == "__main__":
    main()
