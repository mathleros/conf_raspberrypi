from __future__ import annotations

"""Adaptateur entre les skills et le robot matériel.

Le but de ce module est de séparer :
- le code de bas niveau de la Smart Car (GPIO, moteurs, capteur)
- les skills métier de haut niveau (avancer, arrêter, suivre une cible)

Les skills ne doivent pas manipuler directement les GPIO ni dépendre de la
classe concrète `SmartCar2WD`. Elles travaillent avec une interface
homogène exposée par `RobotController`.
"""

from typing import Any


class RobotController:
    """Adaptateur de contrôle du robot.

    Il encapsule la logique d'accès au robot matériel et expose une API
    cohérente pour les skills : forward, backward, left, right, stop,
    check_obstacle, etc.
    """

    def __init__(self, robot: Any):
        self.robot = robot

    def forward(self) -> None:
        """Avance en ligne droite."""
        if hasattr(self.robot, "forward"):
            self.robot.forward()
            return
        raise AttributeError("Le robot ne fournit pas de méthode forward().")

    def backward(self) -> None:
        """Recule en ligne droite."""
        if hasattr(self.robot, "backward"):
            self.robot.backward()
            return
        raise AttributeError("Le robot ne fournit pas de méthode backward().")

    def left(self) -> None:
        """Tourne vers la gauche."""
        if hasattr(self.robot, "left"):
            self.robot.left()
            return
        raise AttributeError("Le robot ne fournit pas de méthode left().")

    def right(self) -> None:
        """Tourne vers la droite."""
        if hasattr(self.robot, "right"):
            self.robot.right()
            return
        raise AttributeError("Le robot ne fournit pas de méthode right().")

    def stop(self) -> None:
        """Arrête les moteurs."""
        if hasattr(self.robot, "stop"):
            self.robot.stop()
            return
        raise AttributeError("Le robot ne fournit pas de méthode stop().")

    def set_speed(self, speed: float) -> None:
        """Applique la vitesse globale si le robot le supporte."""
        if hasattr(self.robot, "set_speed"):
            self.robot.set_speed(speed)
            return
        raise AttributeError("Le robot ne fournit pas de méthode set_speed().")

    def check_obstacle(self) -> bool:
        """Retourne True si un obstacle est détecté."""
        if hasattr(self.robot, "check_obstacle"):
            return bool(self.robot.check_obstacle())
        return False

    def __getattr__(self, name: str):
        """Délègue les attributs non couverts au robot concret.

        Cela permet d'ajouter progressivement des méthodes sans casser le
        contrat de la skill.
        """
        return getattr(self.robot, name)


class MockRobotController(RobotController):
    """Contrôleur de test sans hardware.

    Utile pour exécuter les skills dans un environnement simulé ou lors des
    tests unitaires.
    """

    def __init__(self):
        self.robot = type(
            "MockRobot",
            (),
            {
                "forward": lambda self: None,
                "backward": lambda self: None,
                "left": lambda self: None,
                "right": lambda self: None,
                "stop": lambda self: None,
                "set_speed": lambda self, speed: None,
                "check_obstacle": lambda self: False,
            },
        )()
