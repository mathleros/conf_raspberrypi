"""Pilote matériel d'une voiture 2 roues via un module L298N.

Notes de câblage :
- GPIO 5, 6, 16, 24 sont utilisés pour les entrées IN1, IN2, IN3, IN4
- GPIO 12 et 13 pilotent ENA et ENB (PWM pour la vitesse)
- le GND du Raspberry Pi doit être relié au GND du module L298N
"""

from contextlib import ExitStack
from typing import ClassVar

try:
    from gpiozero import Motor
except ModuleNotFoundError:  # pragma: no cover - relevant on non-Pi hosts only
    Motor = None


class SmartCar2WD:
    """Contrôle une voiture 2 roues motrices (2WD) avec un L298N.

    Les broches GPIO sont celles du mode BCM (Broadcom), pas les numéros de broches
    physiques du connecteur 40 broches.
    """

    DEFAULT_PINS: ClassVar[dict[str, int]] = {
        "in1": 5,
        "in2": 6,
        "in3": 16,
        "in4": 24,
        "ena": 12,
        "enb": 13,
    }

    def __init__(
        self,
        in1=DEFAULT_PINS["in1"],
        in2=DEFAULT_PINS["in2"],
        in3=DEFAULT_PINS["in3"],
        in4=DEFAULT_PINS["in4"],
        ena=DEFAULT_PINS["ena"],
        enb=DEFAULT_PINS["enb"],
        drive_speed: float = 0.5,
        trim_a: float = 1.0,
        trim_b: float = 1.0,
    ):
        # trim_a / trim_b : facteur appliqué à la vitesse du moteur A / B pour
        # compenser une dérive (1.0 = pas de correction, 0.95 = 5 % plus lent).
        self.trim_a = trim_a
        self.trim_b = trim_b
        self.motor_a = Motor(forward=in1, backward=in2, enable=ena, pwm=True)
        self.motor_b = Motor(forward=in3, backward=in4, enable=enb, pwm=True)
        self._closed = False
        self._direction = (0, 0)

        self.speed = self.clamp_speed(drive_speed)
        self.stop()

    @staticmethod
    def clamp_speed(speed: float) -> float:
        """Limite la vitesse à l'intervalle [0.0, 1.0]."""
        return max(0.0, min(1.0, speed))

    def _drive(self, direction_a: int, direction_b: int) -> None:
        """Applique un sens (+1 avant, -1 arrière, 0 arrêt) à chaque moteur, avec trim."""
        self._direction = (direction_a, direction_b)
        self.motor_a.value = direction_a * self.clamp_speed(self.speed * self.trim_a)
        self.motor_b.value = direction_b * self.clamp_speed(self.speed * self.trim_b)

    def set_speed(self, speed: float) -> None:
        """Applique une vitesse globale sur les deux moteurs."""
        self.speed = self.clamp_speed(speed)
        self._drive(*self._direction)

    def forward(self) -> None:
        """Avance en ligne droite."""
        self._drive(1, 1)

    def backward(self) -> None:
        """Recule en ligne droite."""
        self._drive(-1, -1)

    def left(self) -> None:
        """Tourne vers la gauche.

        Le moteur A est inversé tandis que le moteur B avance.
        """
        self._drive(-1, 1)

    def right(self) -> None:
        """Tourne vers la droite.

        Le moteur A avance tandis que le moteur B est inversé.
        """
        self._drive(1, -1)

    def stop(self) -> None:
        """Arrête les moteurs et met la vitesse PWM à zéro."""
        self._direction = (0, 0)
        self.motor_a.stop()
        self.motor_b.stop()

    def cleanup(self) -> None:
        """Arrête le véhicule et libère ses GPIO."""
        if self._closed:
            return
        self._closed = True
        try:
            self.stop()
        finally:
            with ExitStack() as cleanup:
                cleanup.callback(self.motor_a.close)
                cleanup.callback(self.motor_b.close)
