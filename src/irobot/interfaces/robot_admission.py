"""Mission admission and lifecycle; all state belongs to RobotController."""

from __future__ import annotations

from collections.abc import Callable
import math
from typing import TYPE_CHECKING

from irobot.interfaces.protection import (
    AdmissionRequest, HumanConditions, MissionPermit, ProtectionFault, Reservation,
)

if TYPE_CHECKING:
    from irobot.interfaces.robot_controller import RobotController


def admit(
    self: RobotController, *, human: bool = False, deadline: float | None = None,
    conditions: Callable[[], HumanConditions] | None = None,
    request: AdmissionRequest | None = None, acquisition: bool = False,
) -> MissionPermit:
    with self._lock:
        if acquisition and (not human or deadline is not None):
            raise ProtectionFault("invalid_acquisition_reservation")
        self._apply_pending_interrupt()
        request = request if request is not None else self.capture_admission_request()
        _validate_request(self, request, human, deadline, conditions, acquisition)
        armament = _admission_armament(self, request, acquisition)
        if human:
            assert conditions is not None
            _prepare_human(self, conditions, acquisition)
        if self.protection_present:
            _recheck_armament(self, armament)
        return _reserve(self, request, armament, human, deadline, conditions, acquisition)


def _validate_request(
    self: RobotController, request: AdmissionRequest, human: bool, deadline: float | None,
    conditions: Callable[[], HumanConditions] | None, acquisition: bool,
) -> None:
    if (request.generation != self._generation
            or request.interrupt_sequence != self._interrupt_sequence):
        raise ProtectionFault("rearm_required")
    if request.cancellation_sequence != self._cancellation_sequence:
        raise ProtectionFault("obsolete_request")
    if self._reservation is not None:
        raise ProtectionFault("mission_reserved")
    if human and (not self.protection_present or conditions is None):
        raise ProtectionFault("human_capability_unavailable")
    if human:
        assert self._ports is not None
        if self._ports.journal is None:
            raise ProtectionFault("journal_unavailable")
    if human and deadline is None and not acquisition:
        raise ProtectionFault("deadline_required")
    if deadline is not None and (
        isinstance(deadline, bool) or not isinstance(deadline, (int, float))
        or not math.isfinite(deadline) or deadline <= self.time_fn()
    ):
        raise ProtectionFault("deadline")


def _admission_armament(
    self: RobotController, request: AdmissionRequest, acquisition: bool,
) -> str:
    if not self.protection_present:
        return ""
    armament_at_request = request.armament
    self.supervise(defer_proof=acquisition)
    state = self._last_p5
    if (state is None or state.state != "armed"
            or self._ready_armament != state.armament
            or armament_at_request != state.armament):
        raise ProtectionFault("rearm_required")
    return state.armament


def _prepare_human(
    self: RobotController, conditions: Callable[[], HumanConditions], acquisition: bool,
) -> None:
    try:
        facts = self._human_facts(conditions)
        obstacle = self.check_obstacle()
    except ProtectionFault:
        self.stop()
        raise
    except Exception:
        self.priority_one("admission_exception")
        raise
    failures = facts.preparation_failures() if acquisition else facts.failures()
    if obstacle:
        failures += ("obstacle",)
    if failures:
        self.stop()
        raise ProtectionFault("+".join(failures))
    try:
        assert self._ports is not None and self._ports.journal is not None
        self._ports.journal.write({"schema": "lot-a/1", "event": "admission_request",
                                   "request": self._requests, "at": self.time_fn()})
    except Exception as exc:
        self.stop()
        raise ProtectionFault("journal_error") from exc


def _recheck_armament(self: RobotController, armament: str) -> None:
    try:
        state = self._p5()
    except ProtectionFault as exc:
        self.priority_one(str(exc))
        raise
    if state.state != "armed" or state.armament != armament:
        self.priority_one("armament_changed", *state.causes)
        raise ProtectionFault("rearm_required")


def _reserve(
    self: RobotController, request: AdmissionRequest, armament: str, human: bool,
    deadline: float | None, conditions: Callable[[], HumanConditions] | None,
    acquisition: bool,
) -> MissionPermit:
    with self._emission_lock:
        if (self._applied_interrupt != self._interrupt_sequence
                or request.interrupt_sequence != self._interrupt_sequence
                or (self.protection_present and self._ready_armament != armament)):
            self._apply_pending_interrupt()
            raise ProtectionFault("rearm_required")
        if request.cancellation_sequence != self._cancellation_sequence:
            raise ProtectionFault("obsolete_request")
        if deadline is not None and self.time_fn() >= deadline:
            raise ProtectionFault("deadline")
        if self._emergency_event.is_set():
            raise ProtectionFault("stop")
        self._serial += 1
        permit = MissionPermit(self._serial, self._serial, armament, self._generation)
        self._reservation = Reservation(
            permit, human, deadline, conditions,
            phase="acquiring" if acquisition else "active",
        )
        self._pending_causes = ()
        self.causes = ()
    return permit


def finish(self: RobotController, permit: MissionPermit) -> None:
    with self._lock:
        self._apply_pending_interrupt()
        if self._reservation is not None and self._reservation.permit == permit:
            self.stop()
            self._reservation = None


def suspend(self: RobotController, reason: str) -> None:
    with self._lock:
        self.stop()
        if self._reservation is not None:
            self.causes = tuple(dict.fromkeys((*self.causes, reason)))
        if (self._reservation is not None
                and self._reservation.phase in {"active", "acquiring", "holding", "suspended"}):
            self._reservation.phase = "suspended"


def resume(self: RobotController, *, acquisition: bool = False) -> MissionPermit:
    with self._lock:
        reservation = self._reservation
        if reservation is None or not reservation.human or reservation.phase != "suspended":
            raise ProtectionFault("no_resumable_session")
        self.supervise(defer_proof=acquisition)
        if reservation.phase != "suspended":
            raise ProtectionFault("+".join(self.causes))
        assert reservation.conditions is not None
        facts = self._human_facts(reservation.conditions)
        failures = facts.preparation_failures() if acquisition else facts.failures()
        if failures:
            raise ProtectionFault("+".join(failures))
        state = self._p5()
        with self._emission_lock:
            self._apply_pending_interrupt()
            if (reservation is not self._reservation or reservation.phase != "suspended"
                    or state.state != "armed" or state.armament != reservation.permit.armament
                    or self._ready_armament != state.armament):
                raise ProtectionFault("rearm_required")
            if self._emergency_event.is_set():
                raise ProtectionFault("stop")
            if reservation.deadline is not None and self.time_fn() >= reservation.deadline:
                raise ProtectionFault("deadline")
            self._serial += 1
            reservation.permit = MissionPermit(
                reservation.permit.mission, self._serial, reservation.permit.armament,
                self._generation,
            )
            reservation.phase = "acquiring" if acquisition else "active"
            self.causes = ()
            return reservation.permit


def activate_human(self: RobotController, permit: MissionPermit, *, deadline: float | None = None) -> None:
    """Complete stationary preparation; never dispatch a motor command."""
    with self._lock:
        self.supervise(defer_proof=True)
        reservation = self._reservation
        if (reservation is None or not reservation.human
                or reservation.permit != permit
                or reservation.phase not in {"acquiring", "holding"}):
            raise ProtectionFault("invalid_acquisition_reservation")
        now = self.time_fn()
        if reservation.deadline is None:
            if (isinstance(deadline, bool) or not isinstance(deadline, (float, int))
                    or not math.isfinite(deadline) or deadline <= now):
                raise ProtectionFault("deadline_required")
        elif deadline is not None:
            raise ProtectionFault("deadline_unchangeable")
        assert reservation.conditions is not None
        failures = self._human_facts(reservation.conditions).failures()
        if failures:
            raise ProtectionFault("+".join(failures))
        state = self._p5()
        with self._emission_lock:
            self._apply_pending_interrupt()
            if (reservation is not self._reservation
                    or reservation.phase not in {"acquiring", "holding"}
                    or state.state != "armed" or state.armament != permit.armament
                    or self._ready_armament != permit.armament
                    or self._emergency_event.is_set()):
                raise ProtectionFault("activation_invalidated")
            effective_deadline = reservation.deadline if deadline is None else deadline
            if effective_deadline is None or self.time_fn() >= effective_deadline:
                raise ProtectionFault("deadline")
            reservation.deadline = effective_deadline
            reservation.phase = "active"


def hold_human(self: RobotController, permit: MissionPermit) -> None:
    with self._lock:
        self.stop()
        self.supervise(defer_proof=True)
        reservation = self._reservation
        if (reservation is None or not reservation.human
                or reservation.permit != permit or reservation.phase != "active"):
            raise ProtectionFault("invalid_human_hold")
        reservation.phase = "holding"
