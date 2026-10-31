"""Hardware-independent lifecycle for one explicitly requested human-follow session."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import math

from irobot.interfaces.human_perception import (
    AcquisitionAssessment,
    AcquisitionReason,
    AcquisitionStatus,
    HumanMarkerMissionContext,
)
from irobot.interfaces.protection import HumanConditions


class HumanFollowPhase(str, Enum):
    AVAILABLE = "available"
    ACQUIRING = "acquiring"
    ACQUIRED = "acquired"
    ACTIVE = "active"
    HOLDING = "holding"
    SUSPENDED = "suspended"


class AcquisitionMode(str, Enum):
    INITIAL = "initial"
    RESUME = "resume"


@dataclass(frozen=True)
class HumanFollowSnapshot:
    phase: HumanFollowPhase = HumanFollowPhase.AVAILABLE
    context: HumanMarkerMissionContext | None = None
    acquisition_mode: AcquisitionMode | None = None
    acquisition_deadline: float | None = None
    mission_deadline: float | None = None
    causes: tuple[str, ...] = ()
    last_acquisition_reason: str | None = None


@dataclass(frozen=True)
class HumanLifecycleTransition:
    snapshot: HumanFollowSnapshot
    outcome: str | None = None
    ended_mission_id: str | None = None


class HumanFollowLifecycle:
    ACQUISITION_TIMEOUT_SECONDS = 10.0

    def __init__(self) -> None:
        self._snapshot = HumanFollowSnapshot()
        self._last_now: float | None = None

    @property
    def snapshot(self) -> HumanFollowSnapshot:
        return self._snapshot

    def begin(self, context: HumanMarkerMissionContext, *, now: float) -> HumanLifecycleTransition:
        self._require_time(now)
        if self._snapshot.phase is not HumanFollowPhase.AVAILABLE:
            raise RuntimeError("A human-follow session is already reserved")
        if not isinstance(context, HumanMarkerMissionContext):
            raise TypeError("Human-follow session requires a locked marker mission context")
        self._snapshot = HumanFollowSnapshot(
            phase=HumanFollowPhase.ACQUIRING,
            context=context,
            acquisition_mode=AcquisitionMode.INITIAL,
            acquisition_deadline=self._next_acquisition_deadline(now),
        )
        return HumanLifecycleTransition(self._snapshot)

    def record_acquisition(
        self,
        assessment: AcquisitionAssessment,
        *,
        now: float,
    ) -> HumanLifecycleTransition:
        self._require_time(now)
        if not isinstance(assessment, AcquisitionAssessment):
            raise TypeError("Acquisition assessment must be explicit")
        if (not isinstance(assessment.status, AcquisitionStatus)
                or not isinstance(assessment.reason, AcquisitionReason)):
            raise ValueError("Acquisition assessment is incoherent")
        state = self._snapshot
        if (state.phase is not HumanFollowPhase.ACQUIRING
                or state.acquisition_mode is None
                or state.acquisition_deadline is None):
            raise RuntimeError("No human-marker acquisition is in progress")

        if state.mission_deadline is not None and now >= state.mission_deadline:
            return self._finish("deadline")
        if now >= state.acquisition_deadline:
            return self._acquisition_timeout(assessment.reason.value)

        if assessment.status is AcquisitionStatus.ACQUIRED:
            self._snapshot = replace(
                state,
                phase=HumanFollowPhase.ACQUIRED,
                acquisition_deadline=None,
                last_acquisition_reason=assessment.reason.value,
            )
        else:
            self._snapshot = replace(state, last_acquisition_reason=assessment.reason.value)
        return HumanLifecycleTransition(self._snapshot)

    def activate_after_announcement(
        self,
        *,
        now: float,
        mission_deadline: float | None = None,
        conditions: HumanConditions,
    ) -> HumanLifecycleTransition:
        self._require_time(now)
        state = self._snapshot
        if state.phase is not HumanFollowPhase.ACQUIRED or state.acquisition_mode is None:
            raise RuntimeError("Human-follow activation requires completed acquisition")
        self._require_conditions(conditions)
        if state.acquisition_mode is AcquisitionMode.INITIAL:
            if not self._finite_time(mission_deadline) or mission_deadline <= now:
                raise ValueError("Initial human-follow activation requires a future deadline")
            self._snapshot = replace(
                state,
                phase=HumanFollowPhase.ACTIVE,
                acquisition_mode=None,
                mission_deadline=float(mission_deadline),
            )
        else:
            if mission_deadline is not None:
                raise ValueError("A resumed session must retain its original deadline")
            if state.mission_deadline is None or now >= state.mission_deadline:
                return self._finish("deadline")
            self._snapshot = replace(
                state,
                phase=HumanFollowPhase.ACTIVE,
                acquisition_mode=None,
            )
        return HumanLifecycleTransition(self._snapshot)

    def hold(self, *, now: float) -> HumanLifecycleTransition:
        self._require_time(now)
        if self._snapshot.mission_deadline is not None and now >= self._snapshot.mission_deadline:
            return self._finish("deadline")
        if self._snapshot.phase is not HumanFollowPhase.ACTIVE:
            raise RuntimeError("Only an active human-follow session can enter hold")
        self._snapshot = replace(self._snapshot, phase=HumanFollowPhase.HOLDING)
        return HumanLifecycleTransition(self._snapshot)

    def continue_tracking(
        self,
        *,
        now: float,
        conditions: HumanConditions,
    ) -> HumanLifecycleTransition:
        self._require_time(now)
        if self._snapshot.mission_deadline is not None and now >= self._snapshot.mission_deadline:
            return self._finish("deadline")
        if self._snapshot.phase is not HumanFollowPhase.HOLDING:
            raise RuntimeError("Only a held human-follow session can continue")
        failures = self._condition_failures(conditions)
        if failures:
            transition = self.suspend(failures[0], now=now)
            for cause in failures[1:]:
                transition = self.suspend(cause, now=now)
            return transition
        self._snapshot = replace(self._snapshot, phase=HumanFollowPhase.ACTIVE)
        return HumanLifecycleTransition(self._snapshot)

    def suspend(self, cause: str, *, now: float) -> HumanLifecycleTransition:
        self._require_time(now)
        state = self._snapshot
        if state.mission_deadline is not None and now >= state.mission_deadline:
            return self._finish("deadline")
        cause = self._require_cause(cause)
        if state.phase is HumanFollowPhase.SUSPENDED:
            self._snapshot = replace(
                state,
                causes=tuple(dict.fromkeys((*state.causes, cause))),
            )
            return HumanLifecycleTransition(self._snapshot)
        if (state.phase not in {
                HumanFollowPhase.ACTIVE, HumanFollowPhase.HOLDING,
                HumanFollowPhase.ACQUIRING, HumanFollowPhase.ACQUIRED,
        } or state.mission_deadline is None):
            raise RuntimeError("Only an active human-follow session can be suspended")
        self._snapshot = replace(
            state,
            phase=HumanFollowPhase.SUSPENDED,
            acquisition_mode=None,
            acquisition_deadline=None,
            causes=tuple(dict.fromkeys((*state.causes, cause))),
        )
        return HumanLifecycleTransition(self._snapshot)

    def resolve_cause(self, cause: str) -> HumanLifecycleTransition:
        if self._snapshot.phase is not HumanFollowPhase.SUSPENDED:
            raise RuntimeError("Only suspended-session causes can be resolved")
        cause = self._require_cause(cause)
        if cause not in self._snapshot.causes:
            raise ValueError("Cause is not present in the suspended session")
        self._snapshot = replace(
            self._snapshot,
            causes=tuple(item for item in self._snapshot.causes if item != cause),
        )
        return HumanLifecycleTransition(self._snapshot)

    def request_resume(
        self, *, now: float, context_version: str | None = None,
    ) -> HumanLifecycleTransition:
        self._require_time(now)
        state = self._snapshot
        if state.phase is not HumanFollowPhase.SUSPENDED:
            raise RuntimeError("No suspended human-follow session can be resumed")
        if state.causes:
            raise RuntimeError("Suspended-session causes must be explicitly resolved first")
        if state.mission_deadline is None or now >= state.mission_deadline:
            return self._finish("deadline")
        if state.context is None:
            raise RuntimeError("Suspended human-follow session has no marker context")
        self._snapshot = replace(
            state,
            context=(
                replace(state.context, context_version=context_version)
                if context_version is not None else state.context
            ),
            phase=HumanFollowPhase.ACQUIRING,
            acquisition_mode=AcquisitionMode.RESUME,
            acquisition_deadline=self._next_acquisition_deadline(now, state.mission_deadline),
            last_acquisition_reason=None,
        )
        return HumanLifecycleTransition(self._snapshot)

    def expire(self, *, now: float) -> HumanLifecycleTransition:
        self._require_time(now)
        state = self._snapshot
        deadline = state.mission_deadline
        if deadline is not None and now >= deadline:
            return self._finish("deadline")
        if (state.phase is HumanFollowPhase.ACQUIRING
                and state.acquisition_deadline is not None
                and now >= state.acquisition_deadline):
            return self._acquisition_timeout(state.last_acquisition_reason or "no_acquisition_result")
        return HumanLifecycleTransition(state)

    def finish(self, reason: str) -> HumanLifecycleTransition:
        reason = self._require_cause(reason)
        if self._snapshot.phase is HumanFollowPhase.AVAILABLE:
            raise RuntimeError("There is no human-follow session to finish")
        return self._finish(reason)

    def _finish(self, reason: str) -> HumanLifecycleTransition:
        context = self._snapshot.context
        self._snapshot = HumanFollowSnapshot()
        return HumanLifecycleTransition(
            self._snapshot,
            outcome=reason,
            ended_mission_id=context.mission_id if context is not None else None,
        )

    def _acquisition_timeout(self, detail: str) -> HumanLifecycleTransition:
        state = self._snapshot
        if state.acquisition_mode is AcquisitionMode.INITIAL:
            return self._finish("initial_acquisition_timeout")
        if state.acquisition_mode is not AcquisitionMode.RESUME:
            raise RuntimeError("Acquisition timeout has no active acquisition mode")
        self._snapshot = replace(
            state,
            phase=HumanFollowPhase.SUSPENDED,
            acquisition_mode=None,
            acquisition_deadline=None,
            causes=tuple(dict.fromkeys((*state.causes, "reacquisition_timeout"))),
            last_acquisition_reason=detail,
        )
        return HumanLifecycleTransition(self._snapshot, "reacquisition_timeout")

    def _next_acquisition_deadline(self, now: float, mission_deadline: float | None = None) -> float:
        deadline = now + self.ACQUISITION_TIMEOUT_SECONDS
        if not self._finite_time(deadline) or deadline <= now:
            raise ValueError("Monotonic clock cannot represent the acquisition window")
        if mission_deadline is not None:
            deadline = min(deadline, mission_deadline)
        if deadline <= now:
            raise ValueError("Mission deadline leaves no time for acquisition")
        return deadline

    @staticmethod
    def _condition_failures(conditions: HumanConditions) -> tuple[str, ...]:
        if not isinstance(conditions, HumanConditions):
            raise TypeError("Human-follow conditions must be explicit")
        return conditions.failures()

    @classmethod
    def _require_conditions(cls, conditions: HumanConditions) -> None:
        failures = cls._condition_failures(conditions)
        if failures:
            raise RuntimeError("Human-follow preconditions failed: " + "+".join(failures))

    def _require_time(self, value: float) -> None:
        if not self._finite_time(value):
            raise ValueError("Monotonic time must be finite")
        if self._last_now is not None and value < self._last_now:
            raise ValueError("Monotonic time moved backwards")
        self._last_now = float(value)

    @staticmethod
    def _finite_time(value: object) -> bool:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        try:
            return math.isfinite(value)
        except OverflowError:
            return False

    @staticmethod
    def _require_cause(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Lifecycle cause must be a non-empty string")
        return value
