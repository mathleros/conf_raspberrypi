"""Common result contract for camera perception detectors."""

from abc import ABC, abstractmethod

import numpy as np
from numpy.typing import NDArray

from irobot.interfaces.perception_pipeline import ObjectDetection


class Detector(ABC):
    @abstractmethod
    def detect(self, frame_rgb: NDArray[np.uint8]) -> ObjectDetection | None:
        """Return the best detection, including its visual distance if available."""
