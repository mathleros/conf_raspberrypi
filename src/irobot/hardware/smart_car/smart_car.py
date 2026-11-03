"""Pilote matériel d'une voiture 2 roues via un module L298N.

Notes de câblage :
- GPIO 5, 6, 16, 24 sont utilisés pour les entrées IN1, IN2, IN3, IN4
- GPIO 12 et 13 pilotent ENA et ENB (PWM pour la vitesse)
- le GND du Raspberry Pi doit être relié au GND du module L298N
"""

from contextlib import ExitStack

try:
    from gpiozero import DigitalOutputDevice, PWMOutputDevice
except ModuleNotFoundError:  # pragma: no cover - relevant on non-Pi hosts only
    DigitalOutputDevice = None
    PWMOutputDevice = None


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

    def __init__(
        self,
        in1=DEFAULT_PINS["in1"],
        in2=DEFAULT_PINS["in2"],
        in3=DEFAULT_PINS["in3"],
        in4=DEFAULT_PINS["in4"],
        ena=DEFAULT_PINS["ena"],
        enb=DEFAULT_PINS["enb"],
        drive_speed: float = 0.5,
    ):
        self.pins = {
            "in1": DigitalOutputDevice(in1),
            "in2": DigitalOutputDevice(in2),
            "in3": DigitalOutputDevice(in3),
            "in4": DigitalOutputDevice(in4),
        }
        self.ena = PWMOutputDevice(ena, frequency=100)
        self.enb = PWMOutputDevice(enb, frequency=100)
        self._closed = False

        self.speed = self.clamp_speed(drive_speed)
        self.stop()

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
        """Arrête le véhicule et libère ses GPIO."""
        if self._closed:
            return
        self._closed = True
        try:
            self.stop()
        finally:
            with ExitStack() as cleanup:
                for pin in self.pins.values():
                    cleanup.callback(pin.close)
                cleanup.callback(self.ena.close)
                cleanup.callback(self.enb.close)
