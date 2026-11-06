"""Interface en ligne de commande pour piloter une Smart Car."""

import argparse
import time
from contextlib import ExitStack, suppress

from irobot.common.config.settings import load_runtime_settings
from irobot.common.hardware.smart_car.smart_car import SmartCar2WD
from irobot.common.interfaces.robot_controller import RobotController

try:
    from irobot.common.hardware.sensors.hc_sr04 import HC_SR04
except (ModuleNotFoundError, SystemExit):  # pragma: no cover - hors Raspberry Pi
    HC_SR04 = None


def build_parser() -> argparse.ArgumentParser:
    """Crée le parser de ligne de commande."""
    settings = load_runtime_settings()
    parser = argparse.ArgumentParser(
        description="Contrôle d'une voiture Smart Car 2WD sur Raspberry Pi via un pont H-bridge L298N.",
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
        default=settings.obstacle_threshold_cm,
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
    """Exécute une commande via le contrôleur et libère les ressources."""
    if args.duration < -1:
        raise ValueError("La durée doit être >= -1. (-1 = indéfinie)")
    if not 0.0 <= args.speed <= 1.0:
        raise ValueError("La vitesse doit être comprise entre 0.0 et 1.0.")
    if args.obstacle_threshold_cm < 0:
        raise ValueError("Le seuil d'obstacle doit être positif.")

    with ExitStack() as cleanup:
        sensor = HC_SR04() if HC_SR04 is not None else None
        if sensor is not None:
            cleanup.callback(sensor.cleanup)

        car = SmartCar2WD(drive_speed=args.speed)
        cleanup.callback(car.cleanup)
        controller = RobotController(
            car,
            distance_sensor=sensor,
            obstacle_threshold_cm=args.obstacle_threshold_cm,
        )
        command = getattr(controller, args.command)

        if args.command == "stop":
            command()
            print("Commande 'stop' exécutée.")
            return

        command()
        check_obstacles = args.command != "backward"
        if args.duration == -1:
            print(
                f"Commande '{args.command}' en cours indéfiniment "
                f"(vitesse {args.speed:.2f}, seuil obstacle {args.obstacle_threshold_cm:.1f} cm). "
                "Appuie sur Ctrl+C pour stopper.",
            )
            while True:
                if check_obstacles and controller.check_obstacle():
                    _stop_for_obstacle(controller, args.obstacle_threshold_cm)
                    return
                time.sleep(args.obstacle_check_interval)

        if args.duration > 0:
            deadline = time.monotonic() + args.duration
            while time.monotonic() < deadline:
                if check_obstacles and controller.check_obstacle():
                    _stop_for_obstacle(controller, args.obstacle_threshold_cm)
                    return
                time.sleep(args.obstacle_check_interval)

            controller.stop()
            print(
                f"Commande '{args.command}' exécutée pendant {args.duration}s à vitesse {args.speed:.2f}.",
            )
            return

        controller.stop()
        print(f"Commande '{args.command}' arrêtée immédiatement.")


def _stop_for_obstacle(controller: RobotController, threshold_cm: float) -> None:
    controller.stop()
    print(f"Obstacle détecté à moins de {threshold_cm:.1f} cm : arrêt de la voiture.")


def _stop_lgpio_notify_thread() -> None:
    """Arrête le thread daemon de lgpio à la finalisation de Python."""
    try:
        import lgpio
        from gpiozero import Device
    except ImportError:  # pragma: no cover - hors Raspberry Pi
        return

    thread = getattr(lgpio, "_notify_thread", None)
    if thread is None:
        return
    with suppress(Exception):  # Nettoyage best-effort à la finalisation de Python.
        thread.stop()
        if Device.pin_factory is not None:
            Device.pin_factory.close()
        # Contournement d'un défaut de lgpio : le thread de notification n'est pas fermé proprement par l'API publique.
        lgpio._notify_close(thread._notify)  # noqa: SLF001
        thread.join(1.0)


def main() -> None:
    """Point d'entrée du script."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        run_command(args)
    except ValueError as exc:
        parser.error(str(exc))
    except KeyboardInterrupt:
        print("\nInterruption clavier : arrêt des moteurs.")
    finally:
        _stop_lgpio_notify_thread()
