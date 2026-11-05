"""Détection des balles rouges ou jaunes dans une image."""

import math
from typing import TypedDict

import cv2
import numpy as np
from numpy.typing import NDArray

from irobot.interfaces.perception_contracts import ObjectDetection

from .base_detector import Detector
from .distance_estimator import estimate_distance_cm


class BallCandidate(TypedDict):
    bbox: tuple[int, int, int, int]
    area: float
    diameter_px: float


MAX_AREA_RATIO = 0.25
BORDER_MARGIN = 10

COLOR_CONFIG = {
    "red": {
        "hsv_min": np.array((0, 120, 80)),
        "hsv_max": np.array((12, 255, 255)),
        "hsv_min_2": np.array((165, 120, 80)),
        "hsv_max_2": np.array((179, 255, 255)),
        "min_area": 700,
        "min_circularity": 0.55,
        "min_extent": 0.30,
        "min_solidity": 0.75,
        "aspect_min": 0.75,
        "aspect_max": 1.30,
    },
    # Teinte élargie vers le vert : une balle de tennis est jaune-vert.
    "yellow": {
        "hsv_min": np.array((20, 100, 80)),
        "hsv_max": np.array((42, 255, 255)),
        "min_area": 700,
        "min_circularity": 0.55,
        "min_extent": 0.30,
        "min_solidity": 0.75,
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
) -> bool:
    """Indique si un contour coloré correspond à une balle."""
    area = cv2.contourArea(contour)
    x, y, width, height = cv2.boundingRect(contour)
    if x <= BORDER_MARGIN or y <= BORDER_MARGIN:
        return False
    if x + width >= frame.shape[1] - BORDER_MARGIN or y + height >= frame.shape[0] - BORDER_MARGIN:
        return False
    if area > frame.shape[0] * frame.shape[1] * MAX_AREA_RATIO:
        return False

    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return False

    circularity = (4 * np.pi * area) / (perimeter * perimeter)
    aspect = width / height if height else 0.0
    extent = area / (width * height) if width * height else 0.0
    hull_area = cv2.contourArea(cv2.convexHull(contour))
    solidity = area / hull_area if hull_area > 0 else 0.0

    cfg = COLOR_CONFIG[color_name]
    return (
        area >= cfg["min_area"]
        and circularity >= cfg["min_circularity"]
        and cfg["aspect_min"] <= aspect <= cfg["aspect_max"]
        and extent >= cfg["min_extent"]
        and solidity >= cfg["min_solidity"]
    )


def detect_colored_balls(
    frame: NDArray[np.uint8], color_name: str = "red", *, is_rgb: bool = False,
) -> list[BallCandidate]:
    """Détecte les balles et expose leur boîte, aire et diamètre équivalent."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV if is_rgb else cv2.COLOR_BGR2HSV)
    mask = build_mask_for_color(hsv, color_name)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[BallCandidate] = []
    for contour in contours:
        if not classify_colored_contour(contour, frame, color_name):
            continue

        x, y, width, height = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        candidates.append({
            "bbox": (x, y, width, height),
            "area": area,
            "diameter_px": float(np.sqrt(4.0 * area / np.pi)),
        })
    return candidates


def select_largest_ball(candidates: list[BallCandidate]) -> BallCandidate | None:
    """Choisit la plus grande balle détectée."""
    return max(candidates, key=lambda candidate: candidate["area"], default=None)


class ColorDetector(Detector[ObjectDetection]):
    def __init__(
        self,
        color_name: str,
        ball_diameter_cm: float = 6.0,
        focal_px: float = 680.0,
    ) -> None:
        if color_name not in COLOR_CONFIG:
            raise ValueError(f"Couleur non supportée : {color_name}")
        if (not math.isfinite(ball_diameter_cm) or ball_diameter_cm <= 0
                or not math.isfinite(focal_px) or focal_px <= 0):
            raise ValueError("Ball diameter and focal length must be finite and positive")
        self.color_name = color_name
        self.ball_diameter_cm = ball_diameter_cm
        self.focal_px = focal_px

    def detect(self, frame_rgb: NDArray[np.uint8]) -> ObjectDetection | None:
        candidates = detect_colored_balls(frame_rgb, self.color_name, is_rgb=True)
        candidate = select_largest_ball(candidates)
        if candidate is None:
            return None

        x, y, width, height = candidate["bbox"]
        center_x = x + width / 2
        frame_width = frame_rgb.shape[1]
        position = (
            "left" if center_x < frame_width / 3
            else "right" if center_x > 2 * frame_width / 3
            else "center"
        )
        distance = estimate_distance_cm(
            candidate["diameter_px"], self.ball_diameter_cm, self.focal_px,
        )
        return ObjectDetection(
            label=f"{self.color_name}_ball",
            position=position,
            distance_cm=distance,
            distance_visual_cm=distance,
            confidence=0.95,
            diameter_px=candidate["diameter_px"],
            bbox_px=(x, y, width, height),
        )
