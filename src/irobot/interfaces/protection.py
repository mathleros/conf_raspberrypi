"""Logical protection contracts. No hardware adapter or software rearm operation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math
from typing import Protocol


class ProtectionFault(RuntimeError):
    pass


@dataclass(frozen=True)
class ProtectionState:
    state: str
    armament: str
    observed_at: float
    transition_at: float
    causes: tuple[str, ...] = ()


class ProtectionReader(Protocol):
    def read(self) -> ProtectionState | None: ...


class CycleProof(Protocol):
    def emit(self, cycle: int) -> None: ...


class InhibitionRequest(Protocol):
    def request(self, cause: str) -> None: ...


class DecisionJournal(Protocol):
    def write(self, event: dict) -> None: ...


@dataclass(frozen=True)
class ProtectionPorts:
    reader: ProtectionReader
    proof: CycleProof
    inhibition: InhibitionRequest
    max_age: float
    journal: DecisionJournal | None = None

    def __post_init__(self):
        if (isinstance(self.max_age, bool) or not isinstance(self.max_age, (int, float))
                or not math.isfinite(self.max_age) or self.max_age <= 0):
            raise ValueError("P5 freshness budget must be explicit and positive")
        for port, method in ((self.reader, "read"), (self.proof, "emit"), (self.inhibition, "request")):
            if not callable(getattr(port, method, None)):
                raise ValueError(f"Missing protection port: {method}")


@dataclass(frozen=True)
class HumanConditions:
    request_valid: bool = False
    configuration_qualified: bool = False
    terrain_checked: bool = False
    safe_access_demonstrated: bool = False
    protections_qualified: bool = False
    camera_context_valid: bool = False
    marker_acquired: bool = False
    identity_valid: bool = False
    observations_fresh: bool = False
    distance_valid: bool = False
    obstacle_clear: bool = False
    swept_volume_protected: bool = False
    input_audio_ready: bool = False
    output_audio_ready: bool = False
    journal_ready: bool = False
    movement_allowed: bool = False
    limits_valid: bool = False

    def failures(self) -> tuple[str, ...]:
        return tuple(name for name in self.__dataclass_fields__ if getattr(self, name) is not True)

    def preparation_failures(self) -> tuple[str, ...]:
        pending = {"marker_acquired", "identity_valid", "observations_fresh", "distance_valid"}
        return tuple(name for name in self.failures() if name not in pending)


@dataclass(frozen=True)
class HumanMotionLimits:
    """Injected qualification envelope, not a PWM-to-ground-speed conversion."""

    qualification: str
    max_speed_setting: float
    ground_speed_bound_m_s: float
    rotation_rate_bound_rad_s: float | None = None
    max_rotation_angle_rad: float | None = None
    max_rotation_duration_s: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.qualification, str) or not self.qualification.strip():
            raise ValueError("An identified motion qualification is required")
        values = (self.max_speed_setting, self.ground_speed_bound_m_s)
        rotation = (self.rotation_rate_bound_rad_s, self.max_rotation_angle_rad,
                    self.max_rotation_duration_s)
        if any(value is not None for value in rotation):
            if any(value is None for value in rotation):
                raise ValueError("Rotation qualification requires all three bounds")
            values += rotation
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) or value <= 0 for value in values):
            raise ValueError("Motion bounds must be finite and positive")
        if self.max_speed_setting > 1 or self.ground_speed_bound_m_s > 0.15:
            raise ValueError("Motion qualification exceeds the approved ceiling")

    def refusal(self, command: str, speed: float, duration: float | None) -> str | None:
        if (isinstance(speed, bool) or not isinstance(speed, (int, float))
                or not math.isfinite(speed) or not 0 < speed <= self.max_speed_setting):
            return "human_speed_outside_qualification"
        if command == "backward":
            return "human_backward_forbidden"
        if command in {"left", "right"}:
            if (self.rotation_rate_bound_rad_s is None or self.max_rotation_duration_s is None
                    or self.max_rotation_angle_rad is None):
                return "human_rotation_unqualified"
            if (isinstance(duration, bool) or not isinstance(duration, (int, float))
                    or not math.isfinite(duration) or duration <= 0):
                return "human_rotation_unbounded"
            if (duration > self.max_rotation_duration_s
                    or duration * self.rotation_rate_bound_rad_s > self.max_rotation_angle_rad):
                return "human_rotation_outside_qualification"
        elif command not in {"forward", "set_speed"}:
            return "human_command_forbidden"
        return None


@dataclass(frozen=True)
class AdmissionRequest:
    generation: str
    armament: str | None
    interrupt_sequence: int
    cancellation_sequence: int = 0


@dataclass(frozen=True)
class MissionPermit:
    mission: int
    context: int
    armament: str
    generation: str


@dataclass
class Reservation:
    permit: MissionPermit
    human: bool
    deadline: float | None
    conditions: Callable[[], HumanConditions] | None
    phase: str = "active"


def protection_presence(value: str) -> bool:
    if value not in {"absent", "present"}:
        raise ValueError("protection_presence must be 'absent' or 'present'")
    return value == "present"
