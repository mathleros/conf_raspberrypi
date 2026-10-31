from __future__ import annotations

import threading
import time
import math
from dataclasses import replace
from uuid import uuid4
from collections.abc import Callable
from typing import Any

from irobot.interfaces.protection import (
    AdmissionRequest, HumanConditions, MissionPermit, ProtectionFault, ProtectionPorts,
    ProtectionState, Reservation, protection_presence,
)


class RobotController:
    """Adapter between robot business logic and hardware implementation."""

    CONTROL_LOOP_PERIOD_S = 0.02

    def __init__(
        self,
        robot: Any,
        time_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
        *,
        protection: str = "absent",
        ports: ProtectionPorts | None = None,
    ):
        self._robot = robot
        self._protection_present = protection_presence(protection)
        if self.protection_present and ports is None:
            raise ValueError("Protection present: explicit P5/proof/inhibition ports required")
        self._ports = ports
        self.time_fn = time_fn
        self.sleep_fn = sleep_fn
        self._emergency_event = threading.Event()
        self._lock = threading.RLock()
        self._emission_lock = threading.RLock()
        self._interrupt_sequence = 0
        self._applied_interrupt = 0
        self._pending_causes: tuple[str, ...] = ()
        self._interrupt_at = self.time_fn()
        self._reservation: Reservation | None = None
        self._serial = 0
        self._requests = 0
        self._generation = uuid4().hex
        self._cycle = 0
        self._stop_requests = 0
        self._zero_deliveries = 0
        self._locked_at = self.time_fn()
        self._inhibited_at: float | None = None
        self._ready_armament: str | None = None
        self._last_p5: ProtectionState | None = None
        self._known_armaments: dict[str, float] = {}
        self._last_p1_state: tuple[str, float] | None = None
        self.causes: tuple[str, ...] = ()
        if self.protection_present:
            self._stop_and_request_inhibition("startup")

    def _stop_and_request_inhibition(self, cause: str) -> None:
        errors: list[Exception] = []
        try:
            self.stop()
        except Exception as exc:
            errors.append(exc)
        try:
            self._ports.inhibition.request(cause)
        except Exception as exc:
            errors.append(exc)
        if len(errors) == 1:
            raise errors[0]
        if errors:
            raise ExceptionGroup("Stop and inhibition request failed", errors)

    @property
    def protection_present(self) -> bool:
        return self._protection_present

    @property
    def robot(self):
        if self.protection_present:
            raise AttributeError("Underlying motor access forbidden on protected path")
        return self._robot

    @property
    def speed(self):
        return self._robot.speed

    @property
    def reservation(self) -> Reservation | None:
        return replace(self._reservation) if self._reservation is not None else None

    def _p5(self) -> ProtectionState:
        try:
            state = self._ports.reader.read()
        except Exception as exc:
            raise ProtectionFault("p5_read_error") from exc
        now = self.time_fn()
        if state is None:
            raise ProtectionFault("p5_absent")
        if not isinstance(state, ProtectionState):
            raise ProtectionFault("p5_incoherent")
        if state.state not in {"armed", "inhibited"}:
            raise ProtectionFault("p5_unknown")
        if (not isinstance(state.armament, str) or not state.armament
                or isinstance(state.observed_at, bool) or isinstance(state.transition_at, bool)
                or not math.isfinite(state.observed_at)
                or not math.isfinite(state.transition_at)
                or not state.transition_at <= state.observed_at <= now):
            raise ProtectionFault("p5_incoherent")
        previous = self._last_p5
        known_transition = self._known_armaments.get(state.armament)
        if known_transition is not None and known_transition != state.transition_at:
            raise ProtectionFault("p5_replayed")
        if previous is not None and (
            state.observed_at < previous.observed_at
            or state.transition_at < previous.transition_at
            or (state.transition_at == previous.transition_at
                and (state.armament, state.state) != (previous.armament, previous.state))
            or (state.transition_at > previous.transition_at and state.armament == previous.armament)
        ):
            raise ProtectionFault("p5_replayed")
        if now - state.observed_at > self._ports.max_age:
            raise ProtectionFault("p5_stale")
        self._last_p5 = state
        self._known_armaments[state.armament] = state.transition_at
        if state.state == "armed" and state.causes:
            raise ProtectionFault("p5_incoherent")
        if state.state == "inhibited":
            self._ready_armament = None
            if state.observed_at >= self._locked_at:
                self._inhibited_at = state.observed_at
        elif (self._inhibited_at is not None
              and state.transition_at > max(self._locked_at, self._inhibited_at)):
            self._ready_armament = state.armament
        return state

    def priority_one(self, *causes: str) -> None:
        # This gate never waits for perception, a journal, or a cycle callback.
        try:
            with self._emission_lock:
                self._interrupt_sequence += 1
                self._interrupt_at = self.time_fn()
                self._pending_causes = tuple(dict.fromkeys((*self._pending_causes, *causes)))
                if self.protection_present:
                    self._stop_and_request_inhibition("+".join(causes))
                else:
                    self.stop()
        finally:
            with self._lock:
                self._apply_pending_interrupt()
                self._requests += 1

    def _apply_pending_interrupt(self) -> None:
        with self._emission_lock:
            if self._applied_interrupt == self._interrupt_sequence:
                return
            self._applied_interrupt = self._interrupt_sequence
            self.causes = tuple(dict.fromkeys((*self.causes, *self._pending_causes)))
            self._locked_at = self._interrupt_at
            self._ready_armament = None
            self._inhibited_at = None
            if self._reservation is not None:
                self._reservation.phase = "locked"

    def capture_admission_request(self) -> AdmissionRequest:
        """Snapshot at request receipt, before a cycle can observe a new armament."""
        with self._emission_lock:
            armament = (
                self._ready_armament
                if self._applied_interrupt == self._interrupt_sequence else None
            )
            return AdmissionRequest(self._generation, armament, self._interrupt_sequence)

    def admit(
        self, *, human: bool = False, deadline: float | None = None,
        conditions: Callable[[], HumanConditions] | None = None,
        request: AdmissionRequest | None = None,
        acquisition: bool = False,
    ) -> MissionPermit:
        with self._lock:
            if acquisition and (not human or deadline is not None):
                raise ProtectionFault("invalid_acquisition_reservation")
            self._apply_pending_interrupt()
            request = request if request is not None else self.capture_admission_request()
            if (request.generation != self._generation
                    or request.interrupt_sequence != self._interrupt_sequence):
                raise ProtectionFault("rearm_required")
            if self._reservation is not None:
                raise ProtectionFault("mission_reserved")
            if human and (not self.protection_present or conditions is None):
                raise ProtectionFault("human_capability_unavailable")
            if human and self._ports.journal is None:
                raise ProtectionFault("journal_unavailable")
            if human and deadline is None and not acquisition:
                raise ProtectionFault("deadline_required")
            if deadline is not None and (not math.isfinite(deadline) or deadline <= self.time_fn()):
                raise ProtectionFault("deadline")
            armament = ""
            if self.protection_present:
                armament_at_request = request.armament
                self.supervise(defer_proof=acquisition)
                state = self._last_p5
                if (state is None or state.state != "armed"
                        or self._ready_armament != state.armament
                        or armament_at_request != state.armament):
                    raise ProtectionFault("rearm_required")
                armament = state.armament
            if human:
                facts = conditions()
                failures = facts.preparation_failures() if acquisition else facts.failures()
                if failures:
                    raise ProtectionFault("+".join(failures))
                try:
                    self._ports.journal.write({"schema": "lot-a/1", "event": "admission_request",
                                               "request": self._requests, "at": self.time_fn()})
                except Exception as exc:
                    raise ProtectionFault("journal_error") from exc
            if self.protection_present:
                state = self._p5()
                if state.state != "armed" or state.armament != armament:
                    raise ProtectionFault("rearm_required")
            with self._emission_lock:
                if (self._applied_interrupt != self._interrupt_sequence
                        or request.interrupt_sequence != self._interrupt_sequence
                        or (self.protection_present and self._ready_armament != armament)):
                    self._apply_pending_interrupt()
                    raise ProtectionFault("rearm_required")
                if deadline is not None and self.time_fn() >= deadline:
                    raise ProtectionFault("deadline")
                self._serial += 1
                permit = MissionPermit(self._serial, self._serial, armament, self._generation)
                self._reservation = Reservation(
                    permit, human, deadline, conditions,
                    phase="acquiring" if acquisition else "active",
                )
                self._pending_causes = ()
                self.causes = ()
            return permit

    def finish(self, permit: MissionPermit) -> None:
        with self._lock:
            self._apply_pending_interrupt()
            if self._reservation is not None and self._reservation.permit == permit:
                self.stop()
                self._reservation = None

    def suspend(self, reason: str) -> None:
        with self._lock:
            self.stop()
            if (self._reservation is not None
                    and self._reservation.phase in {"active", "acquiring", "holding", "suspended"}):
                self._reservation.phase = "suspended"
                self.causes = tuple(dict.fromkeys((*self.causes, reason)))

    def resume(self, *, acquisition: bool = False) -> MissionPermit:
        with self._lock:
            reservation = self._reservation
            if reservation is None or not reservation.human or reservation.phase != "suspended":
                raise ProtectionFault("no_resumable_session")
            self.supervise(defer_proof=acquisition)
            if reservation.phase != "suspended":
                raise ProtectionFault("+".join(self.causes))
            facts = reservation.conditions()
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

    def activate_human(self, permit: MissionPermit, *, deadline: float | None = None) -> None:
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
            failures = reservation.conditions().failures()
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

    def hold_human(self, permit: MissionPermit) -> None:
        with self._lock:
            self.stop()
            self.supervise(defer_proof=True)
            reservation = self._reservation
            if (reservation is None or not reservation.human
                    or reservation.permit != permit or reservation.phase != "active"):
                raise ProtectionFault("invalid_human_hold")
            reservation.phase = "holding"

    def bind(self, permit: MissionPermit) -> "MissionRobot":
        return MissionRobot(self, permit)

    def valid_result(self, permit: MissionPermit) -> bool:
        reservation = self._reservation
        return (reservation is not None and reservation.permit == permit
                and reservation.phase == "active")

    def _ordinary_stop(self, reservation: Reservation, causes: tuple[str, ...]) -> None:
        self.stop()
        self.causes = tuple(dict.fromkeys((*self.causes, *causes)))
        if reservation.phase not in {"locked", "ended"}:
            reservation.phase = "ended" if any(
                cause in causes for cause in ("stop", "deadline")
            ) else "suspended"

    def supervise(
        self, permit: MissionPermit | None = None,
        command: str | None = None, value: float | None = None,
        events: tuple[str, ...] = (),
        *, defer_proof: bool = False, evaluate: Callable[[], None] | None = None,
    ) -> None:
        with self._lock:
            self._apply_pending_interrupt()
            if command == "stop" or (command == "set_speed" and value == 0):
                self.stop()
                return
            if command is not None and command not in {"forward", "backward", "left", "right", "set_speed"}:
                self.stop()
                raise ProtectionFault("invalid_motor_command")
            if not self.protection_present:
                if command is not None:
                    self._dispatch(command, value)
                return
            reasons: list[str] = []
            journal_error: Exception | None = None
            delivered = False
            reservation = self._reservation
            try:
                try:
                    state = self._p5()
                except ProtectionFault as exc:
                    state = None
                    reasons.append(str(exc))
                p1 = tuple(e for e in events if e in {"P1", "P3", "P6", "control_loss"})
                if state is not None and state.state == "inhibited":
                    reasons.extend(state.causes or ("p5_inhibited",))
                    physical = tuple(cause for cause in state.causes if cause in {"P1", "P3", "P6"})
                    transition = (state.armament, state.transition_at)
                    if physical and transition != self._last_p1_state:
                        p1 += physical
                        self._last_p1_state = transition
                if reservation is not None and reservation.phase != "locked":
                    if state is None or state.state != "armed":
                        p1 += tuple(reasons)
                    elif state.armament != reservation.permit.armament:
                        p1 += ("armament_changed",)
                if p1:
                    self.priority_one(*p1, *events)
                    if (state is not None and state.state == "inhibited"
                            and state.observed_at >= self._locked_at):
                        self._inhibited_at = state.observed_at
                    reasons.extend(p1)
                if reservation is not None:
                    ordinary = [event for event in events if event not in {
                        "P1", "P3", "P6", "control_loss", "confirmation", "resume",
                    }]
                    if self._is_emergency_stop_requested():
                        ordinary.append("stop")
                    if reservation.deadline is not None and self.time_fn() >= reservation.deadline:
                        ordinary.append("deadline")
                    if reservation.human and command == "backward":
                        ordinary.append("human_backward_forbidden")
                    if ordinary:
                        self._ordinary_stop(reservation, tuple(ordinary))
                    if reservation.human:
                        facts = reservation.conditions()
                        failures = (
                            facts.preparation_failures()
                            if reservation.phase == "acquiring" else facts.failures()
                        )
                        if failures:
                            self._ordinary_stop(reservation, failures)
                    if (reservation.deadline is not None
                            and self.time_fn() >= reservation.deadline
                            and "deadline" not in ordinary):
                        self._ordinary_stop(reservation, ("deadline",))
                if command is not None:
                    if reservation is None:
                        reasons.append("no_mission")
                    elif reservation is not self._reservation:
                        reasons.append("obsolete_context")
                    elif permit != reservation.permit:
                        reasons.append("obsolete_context")
                    elif reservation.phase != "active":
                        reasons.extend(self.causes or (reservation.phase,))
                    elif state is None or self._ready_armament != permit.armament:
                        reasons.append("rearm_required")
                    if not reasons:
                        # Re-read after callbacks; a precomputed authorization is not a capability.
                        latest = None
                        try:
                            latest = self._p5()
                            state = latest
                            if latest.state != "armed" or latest.armament != permit.armament:
                                raise ProtectionFault("armament_changed")
                        except ProtectionFault as exc:
                            state = latest
                            reasons.append(str(exc))
                            extra = state.causes if state is not None else ()
                            self.priority_one(str(exc), *extra)
                        if self._is_emergency_stop_requested():
                            self.stop()
                            self.causes = tuple(dict.fromkeys((*self.causes, "stop")))
                            if reservation.phase != "locked":
                                reservation.phase = "ended"
                            reasons.append("stop")
                        if reservation.deadline is not None and self.time_fn() >= reservation.deadline:
                            self.stop()
                            self.causes = tuple(dict.fromkeys((*self.causes, "deadline")))
                            if reservation.phase != "locked":
                                reservation.phase = "ended"
                            reasons.append("deadline")
                        if not self.valid_result(permit):
                            reasons.append("obsolete_context")
                    if not reasons:
                        with self._emission_lock:
                            self._apply_pending_interrupt()
                            if self._emergency_event.is_set():
                                self.causes = tuple(dict.fromkeys((*self.causes, "stop")))
                                if reservation.phase != "locked":
                                    reservation.phase = "ended"
                            if not self.valid_result(permit):
                                reasons.extend(self.causes or ("obsolete_context",))
                                self.stop()
                            else:
                                output = getattr(self._robot, command)
                                if command == "set_speed":
                                    if value is None or not math.isfinite(value):
                                        raise ProtectionFault("invalid_speed")
                                    output(value)
                                else:
                                    output()
                                delivered = True
                    else:
                        self.stop()
                self._apply_pending_interrupt()
                if reservation is not None and reservation.human:
                    try:
                        self._ports.journal.write({
                            "schema": "lot-a/1", "event": "cycle", "at": self.time_fn(),
                            "mission": reservation.permit.mission,
                            "context": reservation.permit.context,
                            "armament": reservation.permit.armament,
                            "phase": reservation.phase, "causes": self.causes,
                            "requested_command": command, "nonzero_delivered": delivered,
                            "stop_requested_count": self._stop_requests,
                            "zero_delivered_count": self._zero_deliveries,
                            "p5": state.state if state else "unknown",
                        })
                    except Exception as exc:
                        self.suspend("journal_error")
                        journal_error = exc
                        reasons.append("journal_error")
                if evaluate is not None:
                    evaluate()
                if not defer_proof:
                    self._cycle += 1
                    self._ports.proof.emit(self._cycle)
            except Exception:
                self.priority_one("cycle_exception")
                raise
            if journal_error is not None:
                raise ProtectionFault("journal_error") from journal_error
            if command is not None and reasons:
                raise ProtectionFault("+".join(dict.fromkeys(reasons)))

    def _dispatch(self, command: str, value: float | None = None) -> None:
        if self.protection_present:
            raise ProtectionFault("internal_entry_forbidden")
        method = getattr(self._robot, command)
        if command == "set_speed":
            method(value)
        else:
            method()

    def forward(self) -> None:
        if self.protection_present:
            return self.supervise(command="forward")
        if hasattr(self.robot, "forward"):
            self.robot.forward()
            return
        raise AttributeError("Le robot ne fournit pas de méthode forward().")

    def backward(self) -> None:
        if self.protection_present:
            return self.supervise(command="backward")
        if hasattr(self.robot, "backward"):
            self.robot.backward()
            return
        raise AttributeError("Le robot ne fournit pas de méthode backward().")

    def left(self) -> None:
        if self.protection_present:
            return self.supervise(command="left")
        if hasattr(self.robot, "left"):
            self.robot.left()
            return
        raise AttributeError("Le robot ne fournit pas de méthode left().")

    def right(self) -> None:
        if self.protection_present:
            return self.supervise(command="right")
        if hasattr(self.robot, "right"):
            self.robot.right()
            return
        raise AttributeError("Le robot ne fournit pas de méthode right().")

    def stop(self) -> None:
        self._stop_requests += 1
        if hasattr(self._robot, "stop"):
            self._robot.stop()
            self._zero_deliveries += 1
            return
        raise AttributeError("Le robot ne fournit pas de méthode stop().")

    def set_speed(self, speed: float) -> None:
        if self.protection_present:
            if speed == 0:
                return self.stop()
            return self.supervise(command="set_speed", value=speed)
        if hasattr(self.robot, "set_speed"):
            self.robot.set_speed(speed)
            return
        raise AttributeError("Le robot ne fournit pas de méthode set_speed().")

    def check_obstacle(self) -> bool:
        if hasattr(self._robot, "check_obstacle"):
            try:
                obstacle = self._robot.check_obstacle()
            except Exception:
                return True
            if obstacle is None:
                return True
            return bool(obstacle)
        return False

    def read_distance_cm(self) -> float | None:
        reader = getattr(self._robot, "read_distance_cm", None)
        if not callable(reader):
            return None
        try:
            return reader()
        except Exception:
            return None

    def request_emergency_stop(self) -> None:
        with self._emission_lock:
            self._emergency_event.set()
            self.stop()

    def clear_emergency_stop(self) -> None:
        with self._emission_lock:
            self._emergency_event.clear()

    def is_emergency_stop_requested(self) -> bool:
        return self._is_emergency_stop_requested()

    def _is_emergency_stop_requested(self) -> bool:
        if self._emergency_event.is_set():
            return True
        detectors = (
            "is_emergency_stop_requested",
            "check_emergency_stop",
            "emergency_stop_requested",
            "stop_requested",
        )
        for name in detectors:
            if not hasattr(self._robot, name):
                continue
            detector = getattr(self._robot, name)
            try:
                value = detector() if callable(detector) else detector
            except Exception:
                return True
            if bool(value):
                return True
        return False

    def _run_motion_for(self, start_motion, duration_seconds: float, check_obstacle: bool = True,
                        permit: MissionPermit | None = None) -> str | None:
        duration = max(0.0, float(duration_seconds))
        try:
            if self._is_emergency_stop_requested():
                return "emergency_stop"
            if check_obstacle and self.check_obstacle():
                return "obstacle"
            if self.protection_present:
                if start_motion.__name__ not in {"forward", "backward", "left", "right"}:
                    raise ProtectionFault("invalid_motion_entry")
                self.supervise(permit, command=start_motion.__name__)
            else:
                start_motion()
            if duration <= 0.0:
                return
            deadline = self.time_fn() + duration
            while True:
                if self.protection_present:
                    self.supervise(permit)
                    if not self.valid_result(permit):
                        raise ProtectionFault("+".join(self.causes or ("obsolete_context",)))
                if self._is_emergency_stop_requested():
                    return "emergency_stop"
                if check_obstacle and self.check_obstacle():
                    return "obstacle"

                remaining = deadline - self.time_fn()
                if remaining <= 0.0:
                    return
                self.sleep_fn(min(self.CONTROL_LOOP_PERIOD_S, remaining))
        finally:
            self.stop()

    def forward_for(self, duration_seconds: float) -> str | None:
        return self._run_motion_for(self.forward, duration_seconds)

    def backward_for(self, duration_seconds: float) -> str | None:
        return self._run_motion_for(self.backward, duration_seconds, check_obstacle=False)

    def left_for(self, duration_seconds: float) -> str | None:
        return self._run_motion_for(self.left, duration_seconds)

    def right_for(self, duration_seconds: float) -> str | None:
        return self._run_motion_for(self.right, duration_seconds)

    def __getattr__(self, name: str):
        if self.protection_present:
            raise AttributeError(f"Delegation forbidden on protected path: {name}")
        return getattr(self.robot, name)


class MissionRobot:
    """Narrow capability: no delegation and no exposed driver."""

    __slots__ = ("__controller", "__permit")

    def __init__(self, controller: RobotController, permit: MissionPermit):
        self.__controller = controller
        self.__permit = permit

    @property
    def speed(self):
        return self.__controller.speed

    def forward(self):
        self.__controller.supervise(self.__permit, "forward")

    def backward(self):
        self.__controller.supervise(self.__permit, "backward")

    def left(self):
        self.__controller.supervise(self.__permit, "left")

    def right(self):
        self.__controller.supervise(self.__permit, "right")

    def stop(self):
        self.__controller.stop()

    def set_speed(self, value: float):
        if value == 0:
            self.stop()
        else:
            self.__controller.supervise(self.__permit, "set_speed", value)

    def check_obstacle(self):
        return self.__controller.check_obstacle()

    def read_distance_cm(self):
        return self.__controller.read_distance_cm()

    def is_emergency_stop_requested(self):
        return (self.__controller.is_emergency_stop_requested()
                or not self.__controller.valid_result(self.__permit))

    def is_protected_result_current(self):
        self.__controller.supervise()
        return self.__controller.valid_result(self.__permit)

    def _for(self, direction: str, duration: float):
        controller = self.__controller
        start = getattr(self, direction)
        return controller._run_motion_for(
            start, duration, check_obstacle=direction != "backward", permit=self.__permit,
        )

    def forward_for(self, duration):
        return self._for("forward", duration)

    def backward_for(self, duration):
        return self._for("backward", duration)

    def left_for(self, duration):
        return self._for("left", duration)

    def right_for(self, duration):
        return self._for("right", duration)
