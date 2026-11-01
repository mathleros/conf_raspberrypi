"""Typed, hardware-independent contracts for human-marker observations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import TYPE_CHECKING, Protocol, TypeGuard

from irobot.config.settings import MarkerIdentity, RuntimeSettings

if TYPE_CHECKING:
    from irobot.interfaces.human_perception import HumanMarkerAcquisition


class ObservationDisposition(str, Enum):
    VALID = "valid"
    ABSENT = "absent"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"
    STALE = "stale"
    FAULT = "fault"


class AcquisitionStatus(str, Enum):
    CONFIRMING = "confirming"
    ACQUIRED = "acquired"
    REJECTED = "rejected"


class AcquisitionReason(str, Enum):
    WAITING_FOR_CONFIRMATIONS = "waiting_for_confirmations"
    ACQUIRED = "acquired"
    OBSERVATION_ABSENT = "observation_absent"
    OBSERVATION_AMBIGUOUS = "observation_ambiguous"
    OBSERVATION_REJECTED = "observation_rejected"
    PERCEPTION_FAULT = "perception_fault"
    STALE = "stale"
    TIMESTAMP_INCOHERENT = "timestamp_incoherent"
    MISSION_MISMATCH = "mission_mismatch"
    CONTEXT_MISMATCH = "context_mismatch"
    IDENTITY_MISMATCH = "identity_mismatch"
    STREAM_CHANGED = "stream_changed"
    DUPLICATE_FRAME = "duplicate_frame"
    FRAME_OUT_OF_ORDER = "frame_out_of_order"
    FRAME_GAP = "frame_gap"
    GEOMETRY_INVALID = "geometry_invalid"


@dataclass(frozen=True)
class MarkerQuality:
    corners_visible: bool
    geometry_valid: bool
    blur_metric: float | None = None
    reprojection_error_px: float | None = None
    obliqueness_deg: float | None = None


@dataclass(frozen=True)
class MarkerObservation:
    """Original capture/result publication times; monotonic, cm and signed bearing degrees."""

    source_id: str
    stream_generation: str
    frame_number: int
    captured_at: float
    published_at: float
    mission_id: str
    context_version: str
    disposition: ObservationDisposition
    identity: MarkerIdentity | None = None
    image_width_px: int | None = None
    image_height_px: int | None = None
    center_x_px: float | None = None
    center_y_px: float | None = None
    bearing_deg: float | None = None
    optical_distance_cm: float | None = None
    robot_clearance_cm: float | None = None
    calibration_version: str | None = None
    quality: MarkerQuality | None = None
    reason: str | None = None


@dataclass(frozen=True)
class AcquisitionAssessment:
    status: AcquisitionStatus
    reason: AcquisitionReason
    confirmations: int
    detail: str | None = None


@dataclass(frozen=True)
class ArucoFrameDetection:
    disposition: ObservationDisposition
    identity: MarkerIdentity | None = None
    corners_px: tuple[tuple[float, float], ...] | None = None
    reason: str | None = None


@dataclass(frozen=True)
class HumanMarkerMissionContext:
    """Immutable mission snapshot of the configured marker identity and context."""

    mission_id: str
    context_version: str
    identity: MarkerIdentity

    def __post_init__(self) -> None:
        if (not isinstance(self.mission_id, str) or not self.mission_id
                or not isinstance(self.context_version, str) or not self.context_version
                or not isinstance(self.identity, MarkerIdentity)):
            raise ValueError("Human marker mission context must be explicit")

    @classmethod
    def from_runtime_settings(
        cls, settings: RuntimeSettings, *, mission_id: str, context_version: str,
    ) -> HumanMarkerMissionContext:
        if not isinstance(settings, RuntimeSettings):
            raise TypeError("Human marker context requires RuntimeSettings")
        if settings.human_marker_identity is None:
            raise ValueError("Human marker identity is not configured")
        return cls(mission_id, context_version, settings.human_marker_identity)

    def new_acquisition(self, *, max_age_seconds: float) -> HumanMarkerAcquisition:
        from irobot.interfaces.human_perception import HumanMarkerAcquisition

        return HumanMarkerAcquisition(
            expected_identity=self.identity, mission_id=self.mission_id,
            context_version=self.context_version, max_age_seconds=max_age_seconds,
        )


@dataclass(frozen=True)
class HumanPerceptionFrame:
    """Opaque pixels with source-owned sequence, capture time and frame publication time."""

    source_id: str
    stream_generation: str
    frame_number: int
    captured_at: float
    published_at: float
    image: object


class HumanPerceptionProvider(Protocol):
    """Return this frame/context's result, retaining capture time and dating result publication."""

    def observe(
        self, frame: HumanPerceptionFrame, *,
        context: HumanMarkerMissionContext,
    ) -> MarkerObservation: ...


class HumanPerceptionStreamFault(RuntimeError):
    """Explicit stream unavailability, distinct from an image without a marker."""

    def __init__(self, reason: str) -> None:
        if not isinstance(reason, str) or not reason:
            raise ValueError("Perception stream fault requires an explicit reason")
        super().__init__(reason)


class HumanPerceptionFrameSource(Protocol):
    """Borrow the latest atomic frame; never close or restart the shared source.

    Reads must not wait for a new capture. An unavailable stream raises
    HumanPerceptionStreamFault; a frozen stream retains its original timestamps.
    No concrete camera adapter is supplied.
    """

    def read_frame(self) -> HumanPerceptionFrame: ...


class ArucoDetectorBackend(Protocol):
    def detectMarkers(self, image: object) -> tuple[object, object, object]: ...


def finite_number(value: object) -> TypeGuard[int | float]:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False
