"""Stationary integration seam. No live perception, speech or motion provider."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import math

from irobot.config.settings import RuntimeSettings
from irobot.interfaces import human_follow_announcements, human_follow_perception
from irobot.interfaces.human_follow_announcements import HumanAnnouncement
from irobot.interfaces.human_lifecycle import (
    HumanFollowLifecycle, HumanFollowPhase, HumanFollowSnapshot,
)
from irobot.interfaces.human_perception import (
    AcquisitionAssessment, AcquisitionStatus, HumanMarkerAcquisition,
    HumanMarkerMissionContext, HumanPerceptionFrame,
    HumanPerceptionFrameSource, HumanPerceptionProvider, MarkerObservation,
)
from irobot.interfaces.protection import (
    DecisionJournal, HumanConditions, ProtectionFault,
)
from irobot.interfaces.robot_controller import RobotController


@dataclass(frozen=True)
class HumanFollowRequest:
    stand_off_cm: float = 150.0
    duration_s: float = 60.0

    def __post_init__(self) -> None:
        for value, lower, upper in (
            (self.stand_off_cm, 120.0, 200.0), (self.duration_s, 10.0, 300.0),
        ):
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not lower <= value <= upper):
                raise ValueError("Human-follow parameters are outside the approved request contract")


class HumanFollowRuntime:
    """Recalculate session decisions from structured inputs, never from a trace verdict.

    Announcement completion is an explicit input from an adapter, not an assertion
    that speech was heard. No adapter is installed by the production runtime.
    """

    def __init__(
        self, robot: RobotController, settings: RuntimeSettings,
        request: HumanFollowRequest, conditions: Callable[[], HumanConditions],
        journal: DecisionJournal, *, max_age_seconds: float | None = None,
        announcement_timeout_seconds: float | None = None,
        frame_source: HumanPerceptionFrameSource | None = None,
        provider: HumanPerceptionProvider | None = None,
    ) -> None:
        if not robot.protection_present:
            raise ProtectionFault("human_capability_unavailable")
        if settings.human_marker_identity is None:
            raise ProtectionFault("human_marker_not_configured")
        if not isinstance(request, HumanFollowRequest):
            raise TypeError("Human-follow request must be validated")
        max_age_seconds, announcement_timeout_seconds = self._validate_inputs(
            settings, max_age_seconds, announcement_timeout_seconds, frame_source, provider,
        )
        self._frame_source = frame_source
        self._provider = provider
        self._context_started_at = robot.time_fn()
        self._last_stream: tuple[str, str] | None = None
        self._retired_streams: set[tuple[str, str]] = set()
        self.robot = robot
        self.request = request
        self._facts = conditions
        self._journal = journal
        self._max_age = max_age_seconds
        self._announcement_timeout = announcement_timeout_seconds
        self._lifecycle = HumanFollowLifecycle()
        self._acquisition: HumanMarkerAcquisition | None = None
        self._assessment: AcquisitionAssessment | None = None
        self._observation: MarkerObservation | None = None
        self.pending_announcement: HumanAnnouncement | None = None
        self._sequence = 0
        self._announcement_sequence = 0
        self._ended_reason: str | None = None
        self._ended_deadline: float | None = None
        self._ended_locked = False
        self.permit = robot.admit(human=True, acquisition=True, conditions=self.conditions)
        self._prepare(settings)

    @staticmethod
    def _validate_inputs(
        settings: RuntimeSettings, max_age_seconds: float | None,
        announcement_timeout_seconds: float | None,
        frame_source: HumanPerceptionFrameSource | None,
        provider: HumanPerceptionProvider | None,
    ) -> tuple[float, float]:
        if max_age_seconds is None:
            max_age_seconds = settings.human_max_age_seconds
        if announcement_timeout_seconds is None:
            announcement_timeout_seconds = settings.human_announcement_timeout_seconds
        if (isinstance(announcement_timeout_seconds, bool)
                or not isinstance(announcement_timeout_seconds, (int, float))
                or not math.isfinite(announcement_timeout_seconds)
                or announcement_timeout_seconds <= 0):
            raise ValueError("Announcement budget must be explicit and positive")
        # Validate resolved budgets before reserving; no default identity.
        HumanMarkerMissionContext.from_runtime_settings(
            settings, mission_id="validation", context_version="validation",
        ).new_acquisition(max_age_seconds=max_age_seconds)
        if (frame_source is None) != (provider is None):
            raise ValueError("A bound frame source and provider must be supplied together")
        if frame_source is not None and not callable(getattr(frame_source, "read_frame", None)):
            raise TypeError("Human runtime requires a structured frame source")
        if provider is not None and not callable(getattr(provider, "observe", None)):
            raise TypeError("Human runtime requires a structured perception provider")
        return max_age_seconds, announcement_timeout_seconds

    def _prepare(self, settings: RuntimeSettings) -> None:
        try:
            context = HumanMarkerMissionContext.from_runtime_settings(
                settings,
                mission_id=f"{self.permit.generation}:{self.permit.mission}",
                context_version=str(self.permit.context),
            )
            self._lifecycle.begin(context, now=self.robot.time_fn())
            self._acquisition = context.new_acquisition(max_age_seconds=self._max_age)
            self._write(
                "reserved", identity={
                    "family": context.identity.family,
                    "dictionary": context.identity.dictionary,
                    "identifier": context.identity.identifier,
                }, stand_off_cm=self.request.stand_off_cm, duration_s=self.request.duration_s,
                max_age_seconds=self._max_age,
                announcement_timeout_seconds=self._announcement_timeout,
            )
            self._announce("acquiring", "Je cherche votre marqueur.")
        except ProtectionFault:
            self.robot.finish(self.permit)
            raise
        except Exception:
            self.robot.priority_one("human_preparation_exception")
            self.robot.finish(self.permit)
            raise

    @property
    def snapshot(self) -> HumanFollowSnapshot:
        return self._lifecycle.snapshot

    def result_metadata(self) -> dict[str, object]:
        state = self.snapshot
        required_action = (
            "manual_rearm_then_new_request" if self._ended_locked else
            "new_request" if self._ended_reason is not None else
            "correct_faults_then_explicit_resume" if state.phase is HumanFollowPhase.SUSPENDED else
            "none"
        )
        return {
            "mission": f"{self.permit.generation}:{self.permit.mission}",
            "context": str(self.permit.context), "armament": self.permit.armament,
            "mission_deadline": (self._ended_deadline if self._ended_reason is not None
                                 else state.mission_deadline),
            "outcome": self._ended_reason if self._ended_reason is not None else state.phase.value,
            "required_action": required_action,
        }

    def _remember_end(self, reason: str, previous: HumanFollowSnapshot | None = None) -> None:
        previous = self.snapshot if previous is None else previous
        reservation = self.robot.reservation
        self._ended_reason = reason
        self._ended_deadline = previous.mission_deadline
        self._ended_locked = reservation is not None and reservation.phase == "locked"

    def conditions(self) -> HumanConditions:
        facts = self._facts()
        if not isinstance(facts, HumanConditions):
            raise TypeError("Human-follow conditions must be explicit")
        valid = (self._assessment is not None
                 and self._assessment.status is AcquisitionStatus.ACQUIRED
                 and self.snapshot.phase in {
                     HumanFollowPhase.ACQUIRED, HumanFollowPhase.ACTIVE, HumanFollowPhase.HOLDING,
                 })
        fresh = (valid and self._observation is not None
                 and 0 <= self.robot.time_fn() - self._observation.captured_at <= self._max_age)
        return replace(
            facts, marker_acquired=valid, identity_valid=valid,
            observations_fresh=fresh, distance_valid=valid,
        )

    def _write(self, event: str, **fields: object) -> None:
        self._sequence += 1
        context = self.snapshot.context
        try:
            self._journal.write({
                "schema": "human-follow/1", "sequence": self._sequence,
                "event": event, "at": self.robot.time_fn(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mission": f"{self.permit.generation}:{self.permit.mission}",
                "context": context.context_version if context else str(self.permit.context),
                "armament": self.permit.armament,
                "phase": self.snapshot.phase.value,
                "mission_deadline": self.snapshot.mission_deadline,
                "causes": self.robot.causes,
                **fields,
            })
        except Exception as exc:
            self.robot.stop()
            self.robot.suspend("journal_error")
            self.pending_announcement = None
            if self.snapshot.context is not None:
                now = self.robot.time_fn()
                if self.snapshot.mission_deadline is None:
                    self._remember_end("journal_error")
                    self.robot.finish(self.permit)
                    self._lifecycle.finish("journal_error")
                elif now >= self.snapshot.mission_deadline:
                    self.robot.suspend("deadline")
                    self._remember_end("deadline")
                    self.robot.finish(self.permit)
                    self._lifecycle.finish("deadline")
                else:
                    self._lifecycle.suspend("journal_error", now=now)
                if self.snapshot.context is None:
                    self._clear_perception()
            raise ProtectionFault("journal_error") from exc

    def _invalidate_announcement(self) -> None:
        human_follow_announcements.invalidate(self)

    def _announce(self, template: str, text: str, *, remaining_s: float | None = None) -> None:
        human_follow_announcements.announce(self, template, text, remaining_s=remaining_s)

    def _announce_acquired(self, now: float) -> None:
        human_follow_announcements.announce_acquired(self, now)

    def _finish(self, reason: str) -> None:
        self.robot.stop()
        ended = self.snapshot.context
        self._remember_end(reason)
        self.robot.finish(self.permit)
        self._lifecycle.finish(reason)
        self._clear_perception()
        self._invalidate_announcement()
        self._write("ended", outcome=reason, ended_mission=ended.mission_id if ended else None)

    def _clear_perception(self) -> None:
        self._acquisition = None
        self._assessment = None
        self._observation = None
        self._frame_source = None
        self._provider = None
        self._last_stream = None
        self._retired_streams.clear()

    def _sync(self) -> None:
        if self.snapshot.context is None:
            return
        reservation = self.robot.reservation
        if reservation is None or reservation.permit != self.permit:
            if self.snapshot.context is not None:
                self._finish("context_invalidated")
        elif reservation.phase in {"locked", "ended"}:
            self._finish("locked" if reservation.phase == "locked"
                         else "stop" if "stop" in self.robot.causes else "deadline")
        elif reservation.phase == "suspended":
            if self.snapshot.mission_deadline is None:
                self._finish("initial_preparation_failed")
            else:
                previous = self.snapshot
                for cause in self.robot.causes:
                    self._lifecycle.suspend(cause, now=self.robot.time_fn())
                if self.snapshot != previous:
                    if self._acquisition is not None:
                        self._acquisition.reset()
                    self._assessment = None
                    self._observation = None
                    self._invalidate_announcement()
                    self._write("suspended")
                    if "announcement_timeout" not in self.robot.causes:
                        self._announce("suspended", self._suspension_text())

    def _suspension_text(self) -> str:
        return human_follow_announcements.suspension_text(self)

    def cycle(
        self, *, events: tuple[str, ...] = (),
        observation: MarkerObservation | None = None,
        frame: HumanPerceptionFrame | None = None,
        provider: HumanPerceptionProvider | None = None,
        completed_announcement: str | None = None,
    ) -> HumanFollowSnapshot:
        try:
            if self._frame_source is not None and any(
                value is not None for value in (observation, frame, provider)
            ):
                raise ValueError("A bound perception session does not accept input overrides")
            if (frame is None) != (provider is None):
                raise ValueError("A perception frame and provider must be supplied together")
            if frame is not None and not isinstance(frame, HumanPerceptionFrame):
                raise TypeError("Human runtime requires a structured perception frame")
            if provider is not None and not callable(getattr(provider, "observe", None)):
                raise TypeError("Human runtime requires a structured perception provider")
            if observation is not None and frame is not None:
                raise ValueError("Supply either a marker observation or a perception frame")
            self._cycle(
                events=events, observation=observation, frame=frame, provider=provider,
                completed_announcement=completed_announcement,
            )
            self.robot.supervise(evaluate=self._sync)
            return self.snapshot
        except Exception as exc:
            if not isinstance(exc, ProtectionFault):
                self.robot.priority_one("human_cycle_exception")
            reservation = self.robot.reservation
            if reservation is None or reservation.phase in {"suspended", "locked", "ended"}:
                self._sync()
            raise

    def _cycle(
        self, *, events: tuple[str, ...],
        observation: MarkerObservation | None,
        frame: HumanPerceptionFrame | None,
        provider: HumanPerceptionProvider | None,
        completed_announcement: str | None,
    ) -> HumanFollowSnapshot:
        if self.snapshot.context is None:
            raise ProtectionFault("no_human_session")
        if events:
            self.robot.stop()
        self.robot.supervise(events=events, defer_proof=True)
        self._sync()
        if self.snapshot.context is None:
            return self.snapshot
        now = self.robot.time_fn()
        if self._wait_expired(now):
            return self.snapshot
        assessed: AcquisitionAssessment | None = None
        if ((frame is not None or self._frame_source is not None)
                and self.snapshot.phase is not HumanFollowPhase.SUSPENDED):
            result = human_follow_perception.process_frame(self, frame, provider)
            if result is None:
                return self.snapshot
            observation, assessed, now = result
        if observation is not None and self.snapshot.phase is not HumanFollowPhase.SUSPENDED:
            self._accept_observation(observation, assessed=assessed, now=now)
        if completed_announcement is not None:
            self._complete_announcement(completed_announcement)
        return self.snapshot

    def _wait_expired(self, now: float) -> bool:
        deadline = self.snapshot.acquisition_deadline
        if deadline is not None and now >= deadline:
            previous = self.snapshot
            transition = self._lifecycle.expire(now=now)
            if transition.ended_mission_id is not None:
                if transition.outcome is None:
                    raise RuntimeError("A terminal acquisition transition requires an outcome")
                self._remember_end(transition.outcome, previous)
                self.robot.finish(self.permit)
                self._clear_perception()
                self._invalidate_announcement()
                self._write("ended", outcome=transition.outcome,
                            ended_mission=transition.ended_mission_id)
            else:
                self.robot.suspend("reacquisition_timeout")
                self._sync()
                self._write("suspended", reason="reacquisition_timeout")
            return True
        pending = self.pending_announcement
        if pending is not None and now >= pending.deadline:
            self.robot.suspend("announcement_timeout")
            self._sync()
            self._write("announcement_failed", reason="announcement_timeout")
            return True
        return False

    def _accept_observation(
        self, observation: MarkerObservation, *,
        assessed: AcquisitionAssessment | None, now: float,
    ) -> None:
        human_follow_perception.accept_observation(self, observation, assessed=assessed, now=now)

    def _complete_announcement(self, completed_announcement: str) -> None:
        human_follow_announcements.complete(self, completed_announcement)

    def resume(self) -> HumanFollowSnapshot:
        self.cycle()
        if self.snapshot.phase is not HumanFollowPhase.SUSPENDED:
            raise ProtectionFault("no_resumable_session")
        self._assessment = None
        self._observation = None
        self.permit = self.robot.resume(acquisition=True)
        for cause in self.snapshot.causes:
            self._lifecycle.resolve_cause(cause)
        self._lifecycle.request_resume(
            now=self.robot.time_fn(), context_version=str(self.permit.context),
        )
        self._context_started_at = self.robot.time_fn()
        context = self.snapshot.context
        if context is None:
            raise ProtectionFault("no_human_context")
        self._acquisition = context.new_acquisition(max_age_seconds=self._max_age)
        self._announce("reacquiring", "Je recherche votre marqueur pour reprendre.")
        self.robot.supervise(evaluate=self._sync)
        return self.snapshot

    def hold(self) -> HumanFollowSnapshot:
        self.robot.hold_human(self.permit)
        self._lifecycle.hold(now=self.robot.time_fn())
        self._write("holding")
        self.robot.supervise(evaluate=self._sync)
        return self.snapshot

    def continue_tracking(self) -> HumanFollowSnapshot:
        self.cycle()
        if self.snapshot.phase is not HumanFollowPhase.HOLDING:
            raise ProtectionFault("human_session_not_holding")
        self.robot.activate_human(self.permit)
        self._lifecycle.continue_tracking(now=self.robot.time_fn(), conditions=self.conditions())
        self._write("tracking")
        self.robot.supervise(evaluate=self._sync)
        return self.snapshot

    def terminate(self, reason: str) -> None:
        if self.snapshot.context is not None:
            self._finish(reason)
