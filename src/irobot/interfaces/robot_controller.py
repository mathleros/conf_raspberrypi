from __future__ import annotations

import threading
import time
import math
from dataclasses import replace
from uuid import uuid4
from collections.abc import Callable
from typing import Any

from irobot.interfaces import robot_admission, robot_motion, robot_supervision
from irobot.interfaces.mission_robot import MissionRobot

from irobot.interfaces.protection import (
    AdmissionRequest, HumanConditions, HumanMotionLimits, MissionPermit, ProtectionFault, ProtectionPorts,
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
        human_motion_limits: HumanMotionLimits | None = None,
    ):
        self._robot = robot
        self._protection_present = protection_presence(protection)
        if self.protection_present and ports is None:
            raise ValueError("Protection present: explicit P5/proof/inhibition ports required")
        self._ports = ports
        if human_motion_limits is not None and not isinstance(human_motion_limits, HumanMotionLimits):
            raise TypeError("Human motion limits must be an explicit qualification envelope")
        self._human_motion_limits = human_motion_limits
        self.time_fn = time_fn
        self.sleep_fn = sleep_fn
        self._emergency_event = threading.Event()
        self._lock = threading.RLock()
        self._emission_lock = threading.RLock()
        self._interrupt_sequence = 0
        self._cancellation_sequence = 0
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
        if not isinstance(state.state, str) or state.state not in {"armed", "inhibited"}:
            raise ProtectionFault("p5_unknown")
        if (not isinstance(state.armament, str) or not state.armament
                or isinstance(state.observed_at, bool) or isinstance(state.transition_at, bool)
                or not isinstance(state.observed_at, (int, float))
                or not isinstance(state.transition_at, (int, float))
                or not math.isfinite(state.observed_at)
                or not math.isfinite(state.transition_at)
                or not isinstance(state.causes, tuple)
                or any(not isinstance(cause, str) or not cause for cause in state.causes)
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
            return AdmissionRequest(self._generation, armament, self._interrupt_sequence,
                                    self._cancellation_sequence)

    def admit(
        self, *, human: bool = False, deadline: float | None = None,
        conditions: Callable[[], HumanConditions] | None = None,
        request: AdmissionRequest | None = None,
        acquisition: bool = False,
    ) -> MissionPermit:
        return robot_admission.admit(
            self, human=human, deadline=deadline, conditions=conditions,
            request=request, acquisition=acquisition,
        )

    def finish(self, permit: MissionPermit) -> None:
        robot_admission.finish(self, permit)

    def suspend(self, reason: str) -> None:
        robot_admission.suspend(self, reason)

    def resume(self, *, acquisition: bool = False) -> MissionPermit:
        return robot_admission.resume(self, acquisition=acquisition)

    def activate_human(self, permit: MissionPermit, *, deadline: float | None = None) -> None:
        """Complete stationary preparation; never dispatch a motor command."""
        robot_admission.activate_human(self, permit, deadline=deadline)

    def hold_human(self, permit: MissionPermit) -> None:
        robot_admission.hold_human(self, permit)

    def bind(self, permit: MissionPermit) -> "MissionRobot":
        return MissionRobot(self, permit)

    def valid_result(self, permit: MissionPermit | None) -> bool:
        reservation = self._reservation
        return (reservation is not None and reservation.permit == permit
                and reservation.phase == "active"
                and self._applied_interrupt == self._interrupt_sequence
                and not self._emergency_event.is_set()
                and (reservation.deadline is None or self.time_fn() < reservation.deadline))

    @staticmethod
    def _human_facts(conditions: Callable[[], HumanConditions]) -> HumanConditions:
        facts = conditions()
        if not isinstance(facts, HumanConditions):
            raise TypeError("Human conditions must return HumanConditions")
        return facts

    def _human_motion_refusal(
        self, command: str, value: float | None, duration: float | None,
    ) -> str | None:
        limits = self._human_motion_limits
        if limits is None:
            return "human_motion_unqualified"
        return limits.refusal(command, value if command == "set_speed" else self.speed, duration)

    def _ordinary_stop(self, reservation: Reservation, causes: tuple[str, ...]) -> None:
        self.stop()
        self.causes = tuple(dict.fromkeys((*self.causes, *causes)))
        if reservation.phase not in {"locked", "ended"}:
            reservation.phase = "ended" if any(
                cause in causes for cause in ("stop", "cancel", "deadline")
            ) else "suspended"

    def supervise(
        self, permit: MissionPermit | None = None,
        command: str | None = None, value: float | None = None,
        events: tuple[str, ...] = (),
        *, defer_proof: bool = False, evaluate: Callable[[], None] | None = None,
        motion_duration: float | None = None, emit_command: bool = True,
        command_deadline: float | None = None,
    ) -> None:
        robot_supervision.supervise(
            self, permit, command, value, events, defer_proof=defer_proof,
            evaluate=evaluate, motion_duration=motion_duration, emit_command=emit_command,
            command_deadline=command_deadline,
        )

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
            if isinstance(speed, (int, float)) and not isinstance(speed, bool) and speed == 0:
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
            except Exception as exc:
                if self.protection_present:
                    raise ProtectionFault("obstacle_sensor_error") from exc
                return True
            if obstacle is None:
                if self.protection_present:
                    raise ProtectionFault("obstacle_sensor_unavailable")
                return True
            if self.protection_present and not isinstance(obstacle, bool):
                raise ProtectionFault("obstacle_sensor_incoherent")
            return bool(obstacle)
        if self.protection_present:
            raise ProtectionFault("obstacle_sensor_unavailable")
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
            self._cancellation_sequence += 1
            self._emergency_event.set()
            self.stop()

    def clear_emergency_stop(self) -> None:
        with self._emission_lock:
            self._emergency_event.clear()

    def is_emergency_stop_requested(self) -> bool:
        return self._is_emergency_stop_requested()

    def _is_emergency_stop_requested(self) -> bool:
        if self.protection_present:
            causes = self._stop_input_causes()
            faults = tuple(cause for cause in causes if cause != "stop")
            if faults:
                raise ProtectionFault("+".join(faults))
            return bool(causes)
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

    def _stop_input_causes(self) -> tuple[str, ...]:
        causes = ["stop"] if self._emergency_event.is_set() else []
        for name in ("is_emergency_stop_requested", "check_emergency_stop",
                     "emergency_stop_requested", "stop_requested"):
            if not hasattr(self._robot, name):
                continue
            detector = getattr(self._robot, name)
            try:
                value = detector() if callable(detector) else detector
            except Exception:
                causes.append("stop_input_error")
            else:
                if not isinstance(value, bool):
                    causes.append("stop_input_invalid")
                elif value:
                    causes.append("stop")
        return tuple(dict.fromkeys(causes))

    def _run_motion_for(self, start_motion: Callable[[], None], duration_seconds: float,
                        check_obstacle: bool = True,
                        permit: MissionPermit | None = None) -> str | None:
        return robot_motion.run_motion_for(
            self, start_motion, duration_seconds, check_obstacle, permit,
        )

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
