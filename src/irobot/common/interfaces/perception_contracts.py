from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from irobot.common.domain.perception import PerceptionTarget


class TargetFrameDetector(Protocol):
    def detect(self, frame_rgb: NDArray[np.uint8], target: PerceptionTarget) -> ObjectDetection | None:
        ...

    def reset(self, target: PerceptionTarget) -> None:
        ...


@dataclass
class ObjectDetection:
    label: str = "object"
    position: str = "UNKNOWN"  # left|center|right|UNKNOWN
    offset_x: float | None = None  # -1 (bord gauche) à 1 (bord droit), 0 = centre de l'image
    distance_cm: float | None = None
    confidence: float = 0.0
    diameter_px: float | None = None
    distance_visual_cm: float | None = None
    bbox_px: tuple[int, int, int, int] | None = None
    cached: bool = False  # True : détection mémorisée ou image déjà fournie, sans nouvelle observation
    identity: str | None = None  # prénom reconnu (visage), None si non identifié


class ObjectPerceptionPipeline(Protocol):
    """Contract for object perception providers used by runtime/controller layers."""

    def detect(self, *, target: PerceptionTarget) -> ObjectDetection | None:
        ...
