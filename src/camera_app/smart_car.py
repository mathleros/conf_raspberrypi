import argparse
import time

try:
    import RPi.GPIO as GPIO
except ModuleNotFoundError as exc:  # pragma: no cover - only relevant on non-Pi hosts
    raise SystemExit(
        "Ce script nécessite le module RPi.GPIO sur un Raspberry Pi. "
        "Installez-le puis relancez le programme."
    ) from exc


class SmartCar2WD:
    """Pilote une voiture 2 roues motrices via un module L298N."""

    def __init__(self, in1=5, in2=6, in3=16, in4=24):
        self.pins = {"in1": in1, "in2": in2, "in3": in3, "in4": in4}

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        for pin in self.pins.values():
            GPIO.setup(pin, GPIO.OUT)

        self.stop()

    def _set_motor_a(self, forward: bool) -> None:
        GPIO.output(self.pins["in1"], GPIO.HIGH if forward else GPIO.LOW)
        GPIO.output(self.pins["in2"], GPIO.LOW if forward else GPIO.HIGH)

    def _set_motor_b(self, forward: bool) -> None:
        GPIO.output(self.pins["in3"], GPIO.HIGH if forward else GPIO.LOW)
        GPIO.output(self.pins["in4"], GPIO.LOW if forward else GPIO.HIGH)

    def forward(self) -> None:
        self._set_motor_a(True)
        self._set_motor_b(True)

    def backward(self) -> None:
        self._set_motor_a(False)
        self._set_motor_b(False)

    def left(self) -> None:
        # Roue droite vers l'avant, roue gauche vers l'arrière.
        self._set_motor_a(False)
        self._set_motor_b(True)

    def right(self) -> None:
        # Roue gauche vers l'avant, roue droite vers l'arrière.
        self._set_motor_a(True)
        self._set_motor_b(False)

    def stop(self) -> None:
        for pin in self.pins.values():
            GPIO.output(pin, GPIO.LOW)

    def cleanup(self) -> None:
        self.stop()
        GPIO.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Contrôle d'une voiture Smart Car 2WD sur Raspberry Pi via L298N"
    )
    parser.add_argument(
        "command",
        choices=["forward", "backward", "left", "right", "stop"],
        help="Commande à exécuter sur la voiture",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Durée d'exécution en secondes (0 = action immédiate puis arrêt)",
    )
    args = parser.parse_args()

    car = SmartCar2WD()

    try:
        action = {
            "forward": car.forward,
            "backward": car.backward,
            "left": car.left,
            "right": car.right,
            "stop": car.stop,
        }[args.command]

        action()
        if args.duration > 0:
            time.sleep(args.duration)
            car.stop()
        print(f"Commande '{args.command}' exécutée.")
    except KeyboardInterrupt:
        print("\nInterruption clavier : arrêt des moteurs.")
    finally:
        car.cleanup()


if __name__ == "__main__":
    main()
