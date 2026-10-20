import argparse
import time

try:
    from gpiozero import DigitalOutputDevice
except ModuleNotFoundError as exc:  # pragma: no cover - only relevant on non-Pi hosts
    raise SystemExit(
        "Ce script nécessite le module gpiozero sur un Raspberry Pi. "
        "Installez-le puis relancez le programme."
    ) from exc


class SmartCar2WD:
    """Pilote une voiture 2 roues motrices via un module L298N."""

    def __init__(self, in1=5, in2=6, in3=16, in4=24):
        self.pins = {
            "in1": DigitalOutputDevice(in1),
            "in2": DigitalOutputDevice(in2),
            "in3": DigitalOutputDevice(in3),
            "in4": DigitalOutputDevice(in4),
        }
        self.stop()

    def _set_motor_a(self, forward: bool) -> None:
        self.pins["in1"].value = 1 if forward else 0
        self.pins["in2"].value = 0 if forward else 1

    def _set_motor_b(self, forward: bool) -> None:
        self.pins["in3"].value = 1 if forward else 0
        self.pins["in4"].value = 0 if forward else 1

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
            pin.off()

    def cleanup(self) -> None:
        self.stop()
        for pin in self.pins.values():
            pin.close()


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
