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
        if not math.isfinite(self.max_age) or self.max_age <= 0:
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


@dataclass(frozen=True)
class AdmissionRequest:
    generation: str
    armament: str | None
    interrupt_sequence: int


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
