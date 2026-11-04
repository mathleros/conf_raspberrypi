"""Base contract for camera perception detectors."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

import numpy as np
from numpy.typing import NDArray

DetectionT = TypeVar("DetectionT", covariant=True)


class Detector(ABC, Generic[DetectionT]):
    @abstractmethod
    def detect(self, frame_rgb: NDArray[np.uint8]) -> DetectionT | None:
        """Return a detection result for the given RGB frame."""
