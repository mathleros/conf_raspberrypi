"""Base contract for camera perception detectors."""

from abc import ABC, abstractmethod

import numpy as np
from numpy.typing import NDArray


class Detector[DetectionT](ABC):
    @abstractmethod
    def detect(self, frame_rgb: NDArray[np.uint8]) -> DetectionT | None:
        """Return a detection result for the given RGB frame."""
