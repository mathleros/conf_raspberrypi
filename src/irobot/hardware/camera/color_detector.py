"""Détection des balles et objets rouges ou jaunes dans une image."""

from typing import Literal, TypedDict

import cv2
import numpy as np
from numpy.typing import NDArray


class ColorCandidate(TypedDict):
    kind: Literal["ball", "object"]
    bbox: tuple[int, int, int, int]
    area: float
    diameter_px: float


MIN_AREA = 300
MAX_AREA_RATIO = 0.25
BORDER_MARGIN = 10

COLOR_CONFIG = {
    "red": {
        "hsv_min": np.array((0, 180, 80)),
        "hsv_max": np.array((8, 255, 255)),
        "hsv_min_2": np.array((172, 180, 80)),
        "hsv_max_2": np.array((179, 255, 255)),
        "min_area": 700,
        "min_circularity": 0.65,
        "min_extent": 0.30,
        "min_solidity": 0.80,
        "aspect_min": 0.75,
        "aspect_max": 1.30,
    },
    "yellow": {
        "hsv_min": np.array((23, 150, 80)),
        "hsv_max": np.array((35, 255, 255)),
        "min_area": 700,
        "min_circularity": 0.65,
        "min_extent": 0.30,
        "min_solidity": 0.80,
        "aspect_min": 0.75,
        "aspect_max": 1.30,
    },
}


def build_mask_for_color(hsv: NDArray[np.uint8], color_name: str) -> NDArray[np.uint8]:
    """Construit le masque HSV de la couleur demandée."""
    cfg = COLOR_CONFIG[color_name]

    if color_name == "red":
        mask1 = cv2.inRange(hsv, cfg["hsv_min"], cfg["hsv_max"])
        mask2 = cv2.inRange(hsv, cfg["hsv_min_2"], cfg["hsv_max_2"])
        return cv2.bitwise_or(mask1, mask2)

    if color_name == "yellow":
        return cv2.inRange(hsv, cfg["hsv_min"], cfg["hsv_max"])

    raise ValueError(f"Couleur non supportée : {color_name}")


def classify_colored_contour(
    contour: NDArray[np.int32], frame: NDArray[np.uint8], color_name: str,
) -> Literal["ball", "object"] | None:
    """Classe un contour selon sa forme et sa taille."""
    area = cv2.contourArea(contour)
    if area < MIN_AREA:
        return None

    x, y, width, height = cv2.boundingRect(contour)
    if x <= BORDER_MARGIN or y <= BORDER_MARGIN:
        return None
    if x + width >= frame.shape[1] - BORDER_MARGIN or y + height >= frame.shape[0] - BORDER_MARGIN:
        return None
    if area > frame.shape[0] * frame.shape[1] * MAX_AREA_RATIO:
        return None

    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return None

    circularity = (4 * np.pi * area) / (perimeter * perimeter)
    aspect = width / height if height else 0.0
    extent = area / (width * height) if width * height else 0.0
    hull_area = cv2.contourArea(cv2.convexHull(contour))
    solidity = area / hull_area if hull_area > 0 else 0.0

    cfg = COLOR_CONFIG[color_name]
    is_ball = (
        area >= cfg["min_area"]
        and circularity >= cfg["min_circularity"]
        and cfg["aspect_min"] <= aspect <= cfg["aspect_max"]
        and extent >= cfg["min_extent"]
        and solidity >= cfg["min_solidity"]
    )
    return "ball" if is_ball else "object"


def detect_colored_objects(
    frame: NDArray[np.uint8], color_name: str = "red", *, is_rgb: bool = False,
) -> list[ColorCandidate]:
    """Détecte les candidats et expose leur boîte, aire et diamètre équivalent."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV if is_rgb else cv2.COLOR_BGR2HSV)
    mask = build_mask_for_color(hsv, color_name)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[ColorCandidate] = []
    for contour in contours:
        kind = classify_colored_contour(contour, frame, color_name)
        if kind is None:
            continue

        x, y, width, height = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        candidates.append({
            "kind": kind,
            "bbox": (x, y, width, height),
            "area": area,
            "diameter_px": float(np.sqrt(4.0 * area / np.pi)),
        })
    return candidates


def select_best_candidate(candidates: list[ColorCandidate]) -> ColorCandidate | None:
    """Choisit la plus grande balle, ou à défaut le plus grand objet."""
    balls = [candidate for candidate in candidates if candidate["kind"] == "ball"]
    if balls:
        return max(balls, key=lambda candidate: candidate["area"])

    objects = [candidate for candidate in candidates if candidate["kind"] == "object"]
    return max(objects, key=lambda candidate: candidate["area"]) if objects else None
