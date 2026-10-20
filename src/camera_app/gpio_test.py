#!/usr/bin/env python3
import argparse
import time

try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Le module RPi.GPIO n'est pas installé. "
        "Exécute d'abord : sudo ./install_rpigpio.sh"
    ) from exc


def test_pin(pin: int, state: bool, duration: float) -> None:
    print(f"Activation du GPIO{pin} ({'HIGH' if state else 'LOW'}) pendant {duration}s")
    GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
    time.sleep(duration)
    GPIO.output(pin, GPIO.LOW)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Teste les sorties GPIO du Raspberry Pi."
    )
    parser.add_argument("pins", nargs="*", type=int, help="Liste des GPIO à tester (ex: 5 6 16 24)")
    parser.add_argument("--duration", type=float, default=0.5, help="Durée d'activation de chaque GPIO en secondes")
    parser.add_argument("--all", action="store_true", help="Teste les GPIO 5, 6, 16, 24 par défaut")
    args = parser.parse_args()

    pins = args.pins or ([5, 6, 16, 24] if args.all else [])
    if not pins:
        parser.error("Aucun GPIO fourni. Exemple : python gpio_test.py 5 6 16 24 --duration 0.5")

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    for pin in pins:
        GPIO.setup(pin, GPIO.OUT)

    try:
        for pin in pins:
            test_pin(pin, True, args.duration)
            time.sleep(0.1)
        print("Test terminé.")
    finally:
        for pin in pins:
            GPIO.output(pin, GPIO.LOW)
        GPIO.cleanup()


if __name__ == "__main__":
    main()
