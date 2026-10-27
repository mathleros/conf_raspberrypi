#!/usr/bin/env python3
import argparse
import time

try:
    from gpiozero import DigitalOutputDevice
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Le module gpiozero n'est pas installé. "
        "Exécute d'abord : uv sync --project ."
    ) from exc


def activate_pin(pin: int, duration: float) -> None:
    output = DigitalOutputDevice(pin)
    print(f"Activation du GPIO{pin} pendant {duration}s")
    output.on()
    time.sleep(duration)
    output.off()
    output.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Teste les sorties GPIO du Raspberry Pi avec gpiozero."
    )
    parser.add_argument("pins", nargs="*", type=int, help="Liste des GPIO à tester (ex: 5 6 16 24)")
    parser.add_argument("--duration", type=float, default=0.5, help="Durée d'activation de chaque GPIO en secondes")
    parser.add_argument("--all", action="store_true", help="Teste les GPIO 5, 6, 16, 24 par défaut")
    args = parser.parse_args()

    pins = args.pins or ([5, 6, 16, 24] if args.all else [])
    if not pins:
        parser.error("Aucun GPIO fourni. Exemple : uv run gpio-test 5 6 16 24 --duration 0.5")

    try:
        for pin in pins:
            activate_pin(pin, args.duration)
            time.sleep(0.1)
        print("Test terminé.")
    except KeyboardInterrupt:
        print("\nInterruption clavier : arrêt du test GPIO.")
    finally:
        for pin in pins:
            try:
                DigitalOutputDevice(pin).close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
