"""Estimation de distance visuelle (balle et pose ArUco), lissage et fusion ultrason."""

from __future__ import annotations

import math
import logging
from collections.abc import Callable


MARKER_SIDE_CM = 8.0
MARKER_FOCAL_PX = 600.0
MARKER_ORIENTED_SIZE_PX = (480, 640)


def estimate_marker_distance_cm(
    corners_px: tuple[tuple[float, float], ...],
    frame_size_px: tuple[int, int] = MARKER_ORIENTED_SIZE_PX,
) -> float | None:
    """Estimate direct range from pose, assuming centred optics without distortion."""
    import cv2
    import numpy as np

    width, height = frame_size_px
    if width <= 0 or height <= 0:
        raise ValueError("Frame dimensions must be positive")
    corners = np.asarray(corners_px, dtype=np.float64)
    if corners.shape != (4, 2) or not np.isfinite(corners).all():
        return None
    contour = corners.astype(np.float32)
    if not cv2.isContourConvex(contour) or cv2.contourArea(contour) <= 0:
        return None
    half_side = MARKER_SIDE_CM / 2
    object_points = np.array(
        [
            (-half_side, -half_side, 0),
            (half_side, -half_side, 0),
            (half_side, half_side, 0),
            (-half_side, half_side, 0),
        ],
        dtype=np.float64,
    )
    # The focal length is provisional at 480x640; this is not lens calibration.
    camera_matrix = np.array(
        [
            (MARKER_FOCAL_PX * width / MARKER_ORIENTED_SIZE_PX[0], 0, width / 2),
            (0, MARKER_FOCAL_PX * height / MARKER_ORIENTED_SIZE_PX[1], height / 2),
            (0, 0, 1),
        ],
        dtype=np.float64,
    )
    try:
        success, _, translation = cv2.solvePnP(
            object_points, corners, camera_matrix, np.zeros(5),
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
    except cv2.error:
        logging.getLogger(__name__).exception("Échec de l'estimation de pose ArUco.")
        return None
    if not success or not np.isfinite(translation).all() or translation[2, 0] <= 0:
        return None
    return float(np.linalg.norm(translation))


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
