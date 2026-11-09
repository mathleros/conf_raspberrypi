"""Shared backlight correction for RGB camera frames."""

import logging
from collections.abc import Mapping
from typing import Protocol

import cv2
import numpy as np
from numpy.typing import NDArray

from irobot.app.config.settings import RuntimeSettings

logger = logging.getLogger(__name__)


class ExposureCamera(Protocol):
    @property
    def camera_controls(self) -> Mapping[str, object]: ...

    def set_controls(self, controls: dict[str, float]) -> None: ...  # noqa: V107


def configure_exposure(camera: ExposureCamera, settings: RuntimeSettings) -> None:
    """Apply exposure compensation after configuration, before starting capture."""
    value = settings.camera_exposure_value
    if value == 0.0:
        return
    if "ExposureValue" not in camera.camera_controls:
        logger.warning(
            "Compensation contre-jour indisponible : ExposureValue non pris en charge "
            "(%g EV demandé). Le traitement CLAHE reste indépendant.", value,
        )
        return
    camera.set_controls({"ExposureValue": value})


class FrameEnhancer:
    def __init__(self, settings: RuntimeSettings) -> None:
        self._clahe = (
            cv2.createCLAHE(clipLimit=settings.camera_clahe_clip_limit, tileGridSize=(8, 8))
            if settings.camera_clahe_enabled else None
        )

    def apply(self, frame_rgb: NDArray[np.uint8]) -> NDArray[np.uint8]:
        if self._clahe is None:
            return frame_rgb
        lab = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2LAB)
        lab[:, :, 0] = self._clahe.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
