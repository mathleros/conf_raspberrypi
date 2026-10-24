from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ObjectDetection:
    label: str = "object"
    position: str = "UNKNOWN"  # left|center|right|UNKNOWN
    distance_cm: float | None = None
    confidence: float = 0.0


class ObjectPerceptionPipeline(Protocol):
    """Contract for object perception providers used by runtime/controller layers."""

    def detect(self, *, target: str | None = None) -> ObjectDetection | None:
        ...
