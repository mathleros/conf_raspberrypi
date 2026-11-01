"""Protected control cycles; no concrete hardware imports or persistent state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import math
from typing import TYPE_CHECKING

from irobot.interfaces.protection import (
    HumanConditions, MissionPermit, ProtectionFault, ProtectionState, Reservation,
)

if TYPE_CHECKING:
    from irobot.interfaces.robot_controller import RobotController


PRIORITY_EVENTS = frozenset({"P1", "P3", "P6", "control_loss"})
SESSION_EVENTS = PRIORITY_EVENTS | {"confirmation", "resume"}


def supervise(
    self: RobotController, permit: MissionPermit | None = None,
    command: str | None = None, value: float | None = None,
    events: tuple[str, ...] = (),
    *, defer_proof: bool = False, evaluate: Callable[[], None] | None = None,
    motion_duration: float | None = None, emit_command: bool = True,
    command_deadline: float | None = None,
) -> None:
    with self._lock:
        self._apply_pending_interrupt()
        zero_speed = (command == "set_speed" and value == 0
                      and (not self.protection_present
                           or (isinstance(value, (int, float)) and not isinstance(value, bool))))
        if command == "stop" or zero_speed:
            self.stop()
            return
        if command is not None and (
            not isinstance(command, str)
            or command not in {"forward", "backward", "left", "right", "set_speed"}
        ):
            self.stop()
            raise ProtectionFault("invalid_motor_command")
        if not self.protection_present:
            if command is not None:
                self._dispatch(command, value)
            return
        cycle = _ProtectionCycle(self, permit, command, value, events, motion_duration,
                                 emit_command, command_deadline)
        cycle.run(defer_proof, evaluate)


@dataclass
class _ProtectionCycle:
    """Transient facts for one cycle under the controller's existing lock."""

    controller: RobotController
    permit: MissionPermit | None
    command: str | None
    value: float | None
    events: tuple[str, ...]
    motion_duration: float | None
    emit_command: bool
    command_deadline: float | None
    reasons: list[str] = field(default_factory=list, init=False)
    journal_error: Exception | None = field(default=None, init=False)
    delivered: bool = field(default=False, init=False)
    state: ProtectionState | None = field(default=None, init=False)
    facts: HumanConditions | None = field(default=None, init=False)
    reservation: Reservation | None = field(default=None, init=False)

    def run(self, defer_proof: bool, evaluate: Callable[[], None] | None) -> None:
        c = self.controller
        self.reservation = c._reservation
        try:
            self._handle_immediate_events()
            self._observe_protection()
            self._check_session()
            if self.command is not None:
                self._check_command_context()
                if not self.reasons:
                    self._journal_request()
                if not self.reasons:
                    self._revalidate_command()
                if not self.reasons:
                    self._emit()
                else:
                    c.stop()
            c._apply_pending_interrupt()
            self._journal_cycle()
            if evaluate is not None:
                evaluate()
            if not defer_proof and self.journal_error is None:
                c._cycle += 1
                assert c._ports is not None
                c._ports.proof.emit(c._cycle)
        except Exception:
            c.priority_one("cycle_exception")
            raise
        if self.journal_error is not None:
            raise ProtectionFault("journal_error") from self.journal_error
        if self.command is not None and self.reasons:
            raise ProtectionFault("+".join(dict.fromkeys(self.reasons)))

    def _ordinary_events(self) -> tuple[str, ...]:
        c = self.controller
        ordinary = tuple(event for event in self.events if event not in SESSION_EVENTS)
        ordinary += c._stop_input_causes()
        r = self.reservation
        if r is not None and r.deadline is not None and c.time_fn() >= r.deadline:
            ordinary += ("deadline",)
        return ordinary

    def _handle_immediate_events(self) -> None:
        c = self.controller
        if any(event in {"stop", "cancel"} for event in self.events):
            c.request_emergency_stop()
        p1 = tuple(e for e in self.events if e in PRIORITY_EVENTS)
        if p1:
            c.priority_one(*p1, *self.events)
            self.reasons.extend(p1)
        if self.reservation is not None:
            immediate = self._ordinary_events()
            if immediate:
                c._ordinary_stop(self.reservation, immediate)

    def _observe_protection(self) -> None:
        c, r = self.controller, self.reservation
        try:
            self.state = c._p5()
        except ProtectionFault as exc:
            self.state = None
            self.reasons.append(str(exc))
        if r is not None and self.reasons:
            c.causes = tuple(dict.fromkeys((*c.causes, *self.reasons)))
        p1 = ()
        state = self.state
        if state is not None and state.state == "inhibited":
            self.reasons.extend(state.causes or ("p5_inhibited",))
            physical = tuple(cause for cause in state.causes if cause in {"P1", "P3", "P6"})
            transition = (state.armament, state.transition_at)
            if physical and transition != c._last_p1_state:
                p1 += physical
                c._last_p1_state = transition
        if r is not None and r.phase != "locked":
            if state is None or state.state != "armed":
                p1 += tuple(self.reasons)
            elif state.armament != r.permit.armament:
                p1 += ("armament_changed",)
        if p1:
            c.priority_one(*p1, *self.events)
            if (state is not None and state.state == "inhibited"
                    and state.observed_at >= c._locked_at):
                c._inhibited_at = state.observed_at
            self.reasons.extend(p1)

    def _check_session(self) -> None:
        c, r = self.controller, self.reservation
        if r is None:
            return
        ordinary = list(self._ordinary_events())
        if (r.human and self.command == "backward"
                and self.permit == r.permit and r.phase == "active"):
            ordinary.append("human_backward_forbidden")
        if ordinary:
            c._ordinary_stop(r, tuple(ordinary))
        if r.human:
            self._check_human_session(r)
        if (r.deadline is not None and c.time_fn() >= r.deadline
                and "deadline" not in ordinary):
            c._ordinary_stop(r, ("deadline",))

    def _check_human_session(self, r: Reservation) -> None:
        c = self.controller
        try:
            obstacle = c.check_obstacle()
        except ProtectionFault as exc:
            c._ordinary_stop(r, (str(exc),))
        else:
            if obstacle:
                c._ordinary_stop(r, ("obstacle",))
        assert r.conditions is not None
        self.facts = c._human_facts(r.conditions)
        failures = (
            self.facts.preparation_failures() if r.phase == "acquiring" else self.facts.failures()
        )
        if failures:
            c._ordinary_stop(r, failures)
        if self.command is not None and self.permit == r.permit and r.phase == "active":
            refusal = c._human_motion_refusal(self.command, self.value, self.motion_duration)
            if refusal:
                c._ordinary_stop(r, (refusal,))

    def _check_command_context(self) -> None:
        c, r = self.controller, self.reservation
        if r is None:
            self.reasons.append("no_mission")
        elif r is not c._reservation:
            self.reasons.append("obsolete_context")
        elif self.permit != r.permit:
            self.reasons.append("obsolete_context")
        elif r.phase != "active":
            self.reasons.extend(c.causes or (r.phase,))
        else:
            assert self.permit is not None
            if self.state is None or c._ready_armament != self.permit.armament:
                self.reasons.append("rearm_required")

    def _journal_request(self) -> None:
        r = self.reservation
        if r is None or not r.human:
            return
        c, permit = self.controller, self.permit
        assert permit is not None
        try:
            assert c._ports is not None and c._ports.journal is not None
            assert c._human_motion_limits is not None
            c._ports.journal.write({
                "schema": "lot-a/1", "event": "command_requested",
                "at": c.time_fn(), "mission": permit.mission,
                "context": permit.context, "armament": permit.armament,
                "requested_command": self.command, "requested_value": self.value,
                "motion_duration": self.motion_duration,
                "qualification": c._human_motion_limits.qualification,
            })
        except Exception as exc:
            c.suspend("journal_error")
            self.journal_error = exc
            self.reasons.append("journal_error")

    def _revalidate_command(self) -> None:
        # Callbacks can invalidate authorization; keep each last-moment gate.
        c, r, permit = self.controller, self.reservation, self.permit
        assert r is not None and permit is not None
        latest = None
        try:
            latest = c._p5()
            self.state = latest
            if latest.state != "armed" or latest.armament != permit.armament:
                raise ProtectionFault("armament_changed")
        except ProtectionFault as exc:
            self.state = latest
            self.reasons.append(str(exc))
            extra = self.state.causes if self.state is not None else ()
            c.priority_one(str(exc), *extra)
        stop_causes = c._stop_input_causes()
        if stop_causes:
            c._ordinary_stop(r, stop_causes)
            self.reasons.extend(stop_causes)
        if r.deadline is not None and c.time_fn() >= r.deadline:
            c.stop()
            c.causes = tuple(dict.fromkeys((*c.causes, "deadline")))
            if r.phase != "locked":
                r.phase = "ended"
            self.reasons.append("deadline")
        if r.human and not self.reasons:
            self._revalidate_human(r)
        if not c.valid_result(permit):
            self.reasons.append("obsolete_context")

    def _revalidate_human(self, r: Reservation) -> None:
        c = self.controller
        assert r.conditions is not None
        assert self.command is not None and self.permit is not None
        self.facts = c._human_facts(r.conditions)
        failures = self.facts.failures()
        try:
            if c.check_obstacle():
                failures += ("obstacle",)
        except ProtectionFault as exc:
            failures += (str(exc),)
        refusal = c._human_motion_refusal(self.command, self.value, self.motion_duration)
        if refusal:
            failures += (refusal,)
        if failures:
            c._ordinary_stop(r, failures)
            self.reasons.extend(failures)
        else:
            try:
                self.state = c._p5()
                if self.state.state != "armed" or self.state.armament != self.permit.armament:
                    raise ProtectionFault("armament_changed")
            except ProtectionFault as exc:
                c.priority_one(str(exc), *(self.state.causes if self.state else ()))
                self.reasons.append(str(exc))

    def _emit(self) -> None:
        c, r = self.controller, self.reservation
        assert r is not None and self.command is not None
        with c._emission_lock:
            c._apply_pending_interrupt()
            if c._emergency_event.is_set():
                c.causes = tuple(dict.fromkeys((*c.causes, "stop")))
                if r.phase != "locked":
                    r.phase = "ended"
            if r.deadline is not None and c.time_fn() >= r.deadline:
                c._ordinary_stop(r, ("deadline",))
            if self.command_deadline is not None and c.time_fn() >= self.command_deadline:
                c._ordinary_stop(r, ("motion_command_expired",))
            if not c.valid_result(self.permit):
                self.reasons.extend(c.causes or ("obsolete_context",))
                c.stop()
            elif self.emit_command:
                output = getattr(c._robot, self.command)
                if self.command == "set_speed":
                    if self.value is None or not math.isfinite(self.value):
                        raise ProtectionFault("invalid_speed")
                    output(self.value)
                else:
                    output()
                self.delivered = True

    def _journal_cycle(self) -> None:
        c, r = self.controller, self.reservation
        if r is None or not r.human:
            return
        try:
            assert c._ports is not None and c._ports.journal is not None
            assert self.facts is not None
            c._ports.journal.write({
                "schema": "lot-a/1", "event": "cycle", "at": c.time_fn(),
                "mission": r.permit.mission, "context": r.permit.context,
                "armament": r.permit.armament, "phase": r.phase, "causes": c.causes,
                "requested_command": self.command, "nonzero_delivered": self.delivered,
                "requested_value": self.value, "motion_duration": self.motion_duration,
                "blocking_conditions": self.facts.failures(),
                "stop_requested_count": c._stop_requests,
                "zero_delivered_count": c._zero_deliveries,
                "p5": self.state.state if self.state else "unknown",
            })
        except Exception as exc:
            c.suspend("journal_error")
            self.journal_error = exc
            self.reasons.append("journal_error")
