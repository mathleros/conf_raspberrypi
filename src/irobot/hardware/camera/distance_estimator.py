"""Estimation de distance à une balle (modèle sténopé), lissage et fusion ultrason."""

from __future__ import annotations

import math
from collections.abc import Callable


def estimate_distance_cm(diameter_px: float | None, ball_diameter_cm: float, focal_px: float) -> float | None:
    """d = focal_px * ball_diameter_cm / diameter_px ; None si l'entrée est invalide."""
    try:
        values = (float(diameter_px), float(ball_diameter_cm), float(focal_px))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in values):
        return None
    diameter, ball_cm, focal = values
    if diameter <= 0 or ball_cm <= 0 or focal <= 0:
        return None
    return focal * ball_cm / diameter


def focal_from_known_distance(diameter_px: float, ball_diameter_cm: float, known_distance_cm: float) -> float | None:
    """Inverse du modèle : focal_px = diameter_px * known_distance_cm / ball_diameter_cm."""
    if diameter_px is None or diameter_px <= 0 or ball_diameter_cm <= 0 or known_distance_cm <= 0:
        return None
    return diameter_px * known_distance_cm / ball_diameter_cm


class ExponentialSmoother:
    """Filtre exponentiel : s = alpha * x + (1 - alpha) * s."""

    def __init__(self, alpha: float = 0.4) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha doit être dans ]0, 1]")
        self.alpha = float(alpha)
        self._value: float | None = None

    def update(self, measure: float | None) -> float | None:
        """Ajoute une mesure ; une mesure None réinitialise le filtre (cible perdue)."""
        if measure is None:
            self._value = None
            return None
        if self._value is None:
            self._value = float(measure)
        else:
            self._value = self.alpha * float(measure) + (1.0 - self.alpha) * self._value
        return self._value

    def reset(self) -> None:
        self._value = None


def fuse_with_ultrasound(
    visual_cm: float | None,
    ultrasound_cm: float | None,
    tolerance: float = 0.25,
) -> float | None:
    """Retourne la mesure ultrason si elle est à ±tolerance de l'estimation visuelle, sinon le visuel."""
    if visual_cm is None or ultrasound_cm is None or ultrasound_cm <= 0:
        return visual_cm
    if abs(ultrasound_cm - visual_cm) <= tolerance * visual_cm:
        return ultrasound_cm
    return visual_cm


DistanceReader = Callable[[], float | None]


def distance_reader_from_robot(robot: object) -> DistanceReader | None:
    """Retourne `robot.read_distance_cm` s'il existe, sinon None (capteur absent)."""
    reader = getattr(robot, "read_distance_cm", None)
    return reader if callable(reader) else None
