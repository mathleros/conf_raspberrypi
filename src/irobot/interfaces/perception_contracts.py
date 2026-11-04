from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class PerceptionTarget(str, Enum):
    RED_BALL = "red_ball"
    YELLOW_BALL = "yellow_ball"
    ANY_BALL = "ball"
    USER_MARKER = "marker"
    FACE = "face"

    @classmethod
    def from_value(cls, value: object) -> PerceptionTarget | None:
        if value is None:
            return None
        aliases = {
            "red": cls.RED_BALL,
            "red_ball": cls.RED_BALL,
            "yellow": cls.YELLOW_BALL,
            "yellow_ball": cls.YELLOW_BALL,
            "ball": cls.ANY_BALL,
            "both": cls.ANY_BALL,
            "marker": cls.USER_MARKER,
            "me": cls.USER_MARKER,
            "face": cls.FACE,
            "human": cls.FACE,
        }
        return aliases.get(str(value).strip().lower())


class TargetFrameDetector(Protocol):
    def detect(self, frame_rgb: NDArray[np.uint8], target: PerceptionTarget) -> ObjectDetection | None:
        ...

    def reset(self, target: PerceptionTarget) -> None:
        ...


@dataclass
class ObjectDetection:
    label: str = "object"
    position: str = "UNKNOWN"  # left|center|right|UNKNOWN
    distance_cm: float | None = None
    confidence: float = 0.0
    diameter_px: float | None = None
    distance_visual_cm: float | None = None
    bbox_px: tuple[int, int, int, int] | None = None


class ObjectPerceptionPipeline(Protocol):
    """Contract for object perception providers used by runtime/controller layers."""

    def detect(self, *, target: PerceptionTarget) -> ObjectDetection | None:
        ...
