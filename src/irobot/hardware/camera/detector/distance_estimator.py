"""Estimation de distance visuelle pour les objets détectés par la caméra."""

from __future__ import annotations

import math


def estimate_distance_cm(diameter_px: float | None, diameter_cm: float, focal_px: float) -> float | None:
    """d = focal_px * diameter_cm / diameter_px ; None si l'entrée est invalide."""
    try:
        values = (float(diameter_px), float(diameter_cm), float(focal_px))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in values):
        return None
    diameter, object_cm, focal = values
    if diameter <= 0 or object_cm <= 0 or focal <= 0:
        return None
    return focal * object_cm / diameter
