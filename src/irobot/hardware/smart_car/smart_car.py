"""Pilote une voiture 2 roues via un module L298N sur Raspberry Pi.

Le programme expose deux modes de commande :
- une commande de direction : forward, backward, left, right, stop
- un réglage de vitesse via --speed (0.0 à 1.0)

Exemples :
    uv run smart-car forward --speed 0.6 --duration 2
    uv run smart-car left --speed 0.4
    uv run smart-car stop

Notes de câblage :
- GPIO 5, 6, 16, 24 sont utilisés pour les entrées IN1, IN2, IN3, IN4
- GPIO 12 et 13 pilotent ENA et ENB (PWM pour la vitesse)
- le GND du Raspberry Pi doit être relié au GND du module L298N
"""

import argparse
import threading
import time

try:
    from gpiozero import DigitalOutputDevice, PWMOutputDevice
except ModuleNotFoundError:  # pragma: no cover - relevant on non-Pi hosts only
    DigitalOutputDevice = None
    PWMOutputDevice = None

try:
    from irobot.hardware.sensors.hc_sr04 import HC_SR04
except (ModuleNotFoundError, SystemExit):  # pragma: no cover - hc_sr04 quitte si gpiozero est absent
    HC_SR04 = None


class SmartCar2WD:
    """Contrôle une voiture 2 roues motrices (2WD) avec un L298N.

    Les broches GPIO sont celles du mode BCM (Broadcom), pas les numéros de broches
    physiques du connecteur 40 broches.
    """

    DEFAULT_PINS = {
        "in1": 5,
        "in2": 6,
        "in3": 16,
        "in4": 24,
        "ena": 12,
        "enb": 13,
    }

    SENSOR_READ_ATTEMPTS = 5
    SENSOR_CACHE_TTL_S = 0.05

    def __init__(
        self,
        in1=DEFAULT_PINS["in1"],
        in2=DEFAULT_PINS["in2"],
        in3=DEFAULT_PINS["in3"],
        in4=DEFAULT_PINS["in4"],
        ena=DEFAULT_PINS["ena"],
        enb=DEFAULT_PINS["enb"],
        obstacle_threshold_cm: float = 20.0,
        sensor_trigger_pin: int = 17,
        sensor_echo_pin: int = 27,
        require_obstacle_sensor: bool = False,
        time_fn=time.monotonic,
        sleep_fn=time.sleep,
    ):
        self._time_fn = time_fn
        self._sleep_fn = sleep_fn
        self.pins = {
            "in1": DigitalOutputDevice(in1),
            "in2": DigitalOutputDevice(in2),
            "in3": DigitalOutputDevice(in3),
            "in4": DigitalOutputDevice(in4),
        }
        self.ena = PWMOutputDevice(ena, frequency=100)
        self.enb = PWMOutputDevice(enb, frequency=100)

        self.speed = 1.0
        self.stop()

        # Un seul lecteur à la fois sur le HC-SR04 (TRIG/ECHO chronométrés à la main).
        self._sensor_lock = threading.Lock()
        self._last_distance_cm: float | None = None
        self._last_distance_at: float | None = None

        self.obstacle_threshold_cm = obstacle_threshold_cm
        self.require_obstacle_sensor = bool(require_obstacle_sensor)
        self.distance_sensor = (
            HC_SR04(
                trigger_pin=sensor_trigger_pin,
                echo_pin=sensor_echo_pin,
            )
            if HC_SR04 is not None
            else None
        )

    @staticmethod
    def clamp_speed(speed: float) -> float:
        """Limite la vitesse à l'intervalle [0.0, 1.0]."""
        return max(0.0, min(1.0, speed))

    def set_speed(self, speed: float) -> None:
        """Applique une vitesse globale sur les deux moteurs."""
        self.speed = self.clamp_speed(speed)
        self.ena.value = self.speed
        self.enb.value = self.speed

    def _set_motor_a(self, forward: bool) -> None:
        """Configure le moteur A (roue gauche ou droite selon le schéma)."""
        self.pins["in1"].value = 1 if forward else 0
        self.pins["in2"].value = 0 if forward else 1
        self.ena.value = self.speed

    def _set_motor_b(self, forward: bool) -> None:
        """Configure le moteur B."""
        self.pins["in3"].value = 1 if forward else 0
        self.pins["in4"].value = 0 if forward else 1
        self.enb.value = self.speed

    def forward(self) -> None:
        """Avance en ligne droite."""
        self._set_motor_a(True)
        self._set_motor_b(True)

    def backward(self) -> None:
        """Recule en ligne droite."""
        self._set_motor_a(False)
        self._set_motor_b(False)

    def left(self) -> None:
        """Tourne vers la gauche.

        Le moteur A est inversé tandis que le moteur B avance.
        """
        self._set_motor_a(False)
        self._set_motor_b(True)

    def right(self) -> None:
        """Tourne vers la droite.

        Le moteur A avance tandis que le moteur B est inversé.
        """
        self._set_motor_a(True)
        self._set_motor_b(False)

    def stop(self) -> None:
        """Arrête les moteurs et met la vitesse PWM à zéro."""
        for pin in self.pins.values():
            pin.off()
        self.ena.value = 0
        self.enb.value = 0

    def cleanup(self) -> None:
        """Libère proprement les ressources GPIO."""
        self.stop()
        for pin in self.pins.values():
            pin.close()
        self.ena.close()
        self.enb.close()
        if self.distance_sensor is not None:
            self.distance_sensor.cleanup()

    def read_distance_cm(self) -> float | None:
        """Lit le HC-SR04 sous verrou ; réutilise une mesure valide de moins de 50 ms."""
        if self.distance_sensor is None:
            return None
        with self._sensor_lock:
            now = self._time_fn()
            if (
                self._last_distance_cm is not None
                and self._last_distance_at is not None
                and 0.0 <= now - self._last_distance_at < self.SENSOR_CACHE_TTL_S
            ):
                return self._last_distance_cm

            distance_cm = self.distance_sensor.read_distance_cm()
            if distance_cm is None:
                self._last_distance_cm = None
                self._last_distance_at = None
                return None
            self._last_distance_cm = distance_cm
            self._last_distance_at = self._time_fn()
            return distance_cm

    def check_obstacle(self) -> bool:
        """Retourne True si un objet est détecté à moins de l seuil configuré."""
        if self.distance_sensor is None and not self.require_obstacle_sensor:
            return False
        if self.distance_sensor is None:
            return True

        # Le HC-SR04 renvoie souvent des mesures manquantes : on réessaie avant de conclure.
        for _ in range(self.SENSOR_READ_ATTEMPTS):
            try:
                distance_cm = self.read_distance_cm()
            except Exception:
                return True
            if distance_cm is not None:
                return distance_cm < self.obstacle_threshold_cm
            self._sleep_fn(0.03)
        return True


def build_parser() -> argparse.ArgumentParser:
    """Crée le parser de ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Contrôle d'une voiture Smart Car 2WD sur Raspberry Pi via un pont H-bridge L298N."
    )
    parser.add_argument(
        "command",
        choices=["forward", "backward", "left", "right", "stop"],
        help="Commande à exécuter sur la voiture.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=-1.0,
        help="Durée en secondes. Par défaut, -1 = indéfinie jusqu'à Ctrl+C. 0 = arrêt immédiat.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Vitesse entre 0.0 (arrêt) et 1.0 (vitesse maximale).",
    )
    parser.add_argument(
        "--obstacle-threshold-cm",
        type=float,
        default=20.0,
        help="Arrête la voiture si le capteur HC-SR04 détecte un objet à moins de X cm.",
    )
    parser.add_argument(
        "--obstacle-check-interval",
        type=float,
        default=0.2,
        help="Intervalle de vérification du capteur en secondes pendant un déplacement.",
    )
    return parser


def run_command(args: argparse.Namespace) -> None:
    """Exécute la commande demandée."""
    if args.duration < -1:
        raise ValueError("La durée doit être >= -1. (-1 = indéfinie)")
    if not 0.0 <= args.speed <= 1.0:
        raise ValueError("La vitesse doit être comprise entre 0.0 et 1.0.")
    if args.obstacle_threshold_cm < 0:
        raise ValueError("Le seuil d'obstacle doit être positif.")

    car = SmartCar2WD(obstacle_threshold_cm=args.obstacle_threshold_cm)
    command_map = {
        "forward": car.forward,
        "backward": car.backward,
        "left": car.left,
        "right": car.right,
        "stop": car.stop,
    }

    try:
        car.set_speed(args.speed)
        command = command_map[args.command]

        if args.command == "stop":
            command()
            print("Commande 'stop' exécutée.")
            return

        command()
        # Le recul n'est jamais interrompu par le capteur avant (HC-SR04 orienté vers l'avant)
        check_obstacles = args.command != "backward"

        if args.duration == -1:
            print(
                f"Commande '{args.command}' en cours indéfiniment "
                f"(vitesse {args.speed:.2f}, seuil obstacle {args.obstacle_threshold_cm:.1f} cm). "
                "Appuie sur Ctrl+C pour stopper."
            )
            while True:
                if check_obstacles and car.check_obstacle():
                    print(f"Obstacle détecté à moins de {args.obstacle_threshold_cm:.1f} cm : arrêt de la voiture.")
                    car.stop()
                    break
                time.sleep(args.obstacle_check_interval)
            return

        if args.duration > 0:
            deadline = time.monotonic() + args.duration
            while time.monotonic() < deadline:
                if check_obstacles and car.check_obstacle():
                    print(f"Obstacle détecté à moins de {args.obstacle_threshold_cm:.1f} cm : arrêt de la voiture.")
                    car.stop()
                    return
                time.sleep(args.obstacle_check_interval)

            car.stop()
            print(
                f"Commande '{args.command}' exécutée pendant {args.duration}s à vitesse {args.speed:.2f}."
            )
            return

        car.stop()
        print(f"Commande '{args.command}' arrêtée immédiatement.")
    except KeyboardInterrupt:
        print("\nInterruption clavier : arrêt des moteurs.")
    finally:
        car.stop()
        car.cleanup()


def _stop_lgpio_notify_thread() -> None:
    """Arrête le thread daemon de lgpio pour éviter un crash à la finalisation de Python."""
    try:
        import lgpio
        from gpiozero import Device
    except ImportError:  # pragma: no cover - hors Raspberry Pi
        return

    thread = getattr(lgpio, "_notify_thread", None)
    if thread is None:
        return
    try:
        thread.stop()
        if Device.pin_factory is not None:
            Device.pin_factory.close()
        lgpio._notify_close(thread._notify)
        thread.join(1.0)
    except Exception:
        pass


def main() -> None:
    """Point d'entrée du script."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        run_command(args)
    except ValueError as exc:
        parser.error(str(exc))
    finally:
        _stop_lgpio_notify_thread()


if __name__ == "__main__":
    main()
