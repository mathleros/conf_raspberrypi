from __future__ import annotations

from dataclasses import dataclass

from irobot.interfaces.perception_pipeline import ObjectDetection, ObjectPerceptionPipeline


@dataclass
class SimulatedObjectPerception(ObjectPerceptionPipeline):
    """Simple deterministic object perception sequence for Mac-side simulation."""

    sequence: tuple[ObjectDetection, ...]
    loop: bool = True

    def __post_init__(self):
        self._idx = 0

    def detect(self, *, target: str | None = None) -> ObjectDetection | None:
        if not self.sequence:
            return None
        current = self.sequence[self._idx]
        if self.loop:
            self._idx = (self._idx + 1) % len(self.sequence)
        else:
            self._idx = min(self._idx + 1, len(self.sequence) - 1)
        if target and current.label not in {target, "object"}:
            return ObjectDetection(label=target, position="UNKNOWN", distance_cm=None, confidence=0.0)
        return current
