"""Stationary integration seam. No live perception, speech or motion provider."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import math

from irobot.config.settings import RuntimeSettings
from irobot.interfaces.human_lifecycle import (
    HumanFollowLifecycle, HumanFollowPhase, HumanFollowSnapshot,
)
from irobot.interfaces.human_perception import (
    AcquisitionAssessment, AcquisitionStatus, HumanMarkerAcquisition,
    HumanMarkerMissionContext, MarkerObservation,
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


@dataclass(frozen=True)
class HumanAnnouncement:
    token: str
    mission_id: str
    context_version: str
    template: str
    text: str
    prepared_at: float
    deadline: float
    remaining_s: float | None = None


class HumanFollowRuntime:
    """Recalculate session decisions from structured inputs, never from a trace verdict.

    Announcement completion is an explicit input from an adapter, not an assertion
    that speech was heard. No adapter is installed by the production runtime.
    """

    def __init__(
        self, robot: RobotController, settings: RuntimeSettings,
        request: HumanFollowRequest, conditions: Callable[[], HumanConditions],
        journal: DecisionJournal, *, max_age_seconds: float,
        announcement_timeout_seconds: float,
    ) -> None:
        if not robot.protection_present:
            raise ProtectionFault("human_capability_unavailable")
        if settings.human_marker_identity is None:
            raise ProtectionFault("human_marker_not_configured")
        if not isinstance(request, HumanFollowRequest):
            raise TypeError("Human-follow request must be validated")
        if (isinstance(announcement_timeout_seconds, bool)
                or not isinstance(announcement_timeout_seconds, (int, float))
                or not math.isfinite(announcement_timeout_seconds)
                or announcement_timeout_seconds <= 0):
            raise ValueError("Announcement budget must be explicit and positive")
        # Validate before reserving; no default identity or freshness budget.
        HumanMarkerMissionContext.from_runtime_settings(
            settings, mission_id="validation", context_version="validation",
        ).new_acquisition(max_age_seconds=max_age_seconds)
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
        self.permit = robot.admit(human=True, acquisition=True, conditions=self.conditions)
        try:
            context = HumanMarkerMissionContext.from_runtime_settings(
                settings,
                mission_id=f"{self.permit.generation}:{self.permit.mission}",
                context_version=str(self.permit.context),
            )
            self._lifecycle.begin(context, now=robot.time_fn())
            self._acquisition = context.new_acquisition(max_age_seconds=max_age_seconds)
            self._write(
                "reserved", identity={
                    "family": context.identity.family,
                    "dictionary": context.identity.dictionary,
                    "identifier": context.identity.identifier,
                }, stand_off_cm=request.stand_off_cm, duration_s=request.duration_s,
            )
            self._announce("acquiring", "Je cherche votre marqueur.")
        except Exception:
            robot.priority_one("human_preparation_exception")
            robot.finish(self.permit)
            raise

    @property
    def snapshot(self) -> HumanFollowSnapshot:
        return self._lifecycle.snapshot

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
                if self.snapshot.mission_deadline is None:
                    self.robot.finish(self.permit)
                    self._lifecycle.finish("journal_error")
                    self._acquisition = None
                    self._assessment = None
                    self._observation = None
                else:
                    self._lifecycle.suspend("journal_error", now=self.robot.time_fn())
            raise ProtectionFault("journal_error") from exc

    def _invalidate_announcement(self) -> None:
        previous = self.pending_announcement
        self.pending_announcement = None
        if previous is not None:
            self._write("announcement_invalidated", token=previous.token)

    def _announce(self, template: str, text: str, *, remaining_s: float | None = None) -> None:
        self._invalidate_announcement()
        context = self.snapshot.context
        if context is None:
            raise ProtectionFault("no_human_context")
        self._announcement_sequence += 1
        now = self.robot.time_fn()
        self.pending_announcement = HumanAnnouncement(
            f"{context.mission_id}:{context.context_version}:{self._announcement_sequence}",
            context.mission_id, context.context_version, template, text,
            now, now + self._announcement_timeout, remaining_s,
        )
        self._write("announcement_prepared", template=template,
                    token=self.pending_announcement.token, remaining_s=remaining_s)

    def _finish(self, reason: str) -> None:
        self.robot.stop()
        ended = self.snapshot.context
        self.robot.finish(self.permit)
        self._lifecycle.finish(reason)
        self._acquisition = None
        self._assessment = None
        self._observation = None
        self._invalidate_announcement()
        self._write("ended", outcome=reason, ended_mission=ended.mission_id if ended else None)

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
                    self._invalidate_announcement()
                    self._write("suspended")
                    if "announcement_timeout" not in self.robot.causes:
                        self._announce("suspended", self._suspension_text())

    def _suspension_text(self) -> str:
        messages = {
            "observation_absent": ("Marqueur perdu", "Rendez votre marqueur visible."),
            "observation_ambiguous": (
                "Identifiant attendu en plusieurs exemplaires",
                "Ne laissez visible qu'un exemplaire du marqueur configuré.",
            ),
            "stale": ("Image périmée", "Rétablissez la caméra."),
            "observations_fresh": ("Image périmée", "Rétablissez la caméra."),
            "obstacle": ("Obstacle détecté", "Dégagez l'obstacle."),
            "obstacle_clear": ("Obstacle détecté", "Dégagez l'obstacle."),
            "output_audio_ready": ("Sortie audio défaillante", "Rétablissez l'audio."),
            "input_audio_ready": ("Entrée audio défaillante", "Rétablissez l'audio."),
        }
        cause = self.robot.causes[0] if self.robot.causes else ""
        reason, correction = messages.get(cause, ("Défaut signalé", "Vérifiez le défaut signalé."))
        return f"{reason}, suivi suspendu. {correction} Dites : reprends le suivi."

    def cycle(
        self, *, events: tuple[str, ...] = (),
        observation: MarkerObservation | None = None,
        completed_announcement: str | None = None,
    ) -> HumanFollowSnapshot:
        try:
            self._cycle(
                events=events, observation=observation,
                completed_announcement=completed_announcement,
            )
            self.robot.supervise(evaluate=self._sync)
            return self.snapshot
        except Exception:
            reservation = self.robot.reservation
            if reservation is None or reservation.phase in {"suspended", "locked", "ended"}:
                self._sync()
            raise

    def _cycle(
        self, *, events: tuple[str, ...],
        observation: MarkerObservation | None,
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
        deadline = self.snapshot.acquisition_deadline
        if deadline is not None and now >= deadline:
            transition = self._lifecycle.expire(now=now)
            if transition.ended_mission_id is not None:
                self.robot.finish(self.permit)
                self._acquisition = None
                self._assessment = None
                self._observation = None
                self._invalidate_announcement()
                self._write("ended", outcome=transition.outcome,
                            ended_mission=transition.ended_mission_id)
            else:
                self.robot.suspend("reacquisition_timeout")
                self._sync()
                self._write("suspended", reason="reacquisition_timeout")
            return self.snapshot
        pending = self.pending_announcement
        if pending is not None and now >= pending.deadline:
            self.robot.suspend("announcement_timeout")
            self._sync()
            self._write("announcement_failed", reason="announcement_timeout")
            return self.snapshot
        if observation is not None and self.snapshot.phase is not HumanFollowPhase.SUSPENDED:
            if self._acquisition is None:
                raise ProtectionFault("no_human_acquisition")
            if not isinstance(observation, MarkerObservation):
                raise TypeError("Human runtime requires a structured marker observation")
            self._assessment = self._acquisition.observe(observation, now=now)
            self._observation = observation
            self._write(
                "observation_assessed", reason=self._assessment.reason.value,
                confirmations=self._assessment.confirmations,
                frame=observation.frame_number, captured_at=observation.captured_at,
                source=observation.source_id, stream=observation.stream_generation,
                calibration=observation.calibration_version,
                identity_matches=observation.identity == self.snapshot.context.identity,
                robot_clearance_cm=observation.robot_clearance_cm,
                optical_distance_cm=observation.optical_distance_cm,
                age_s=now - observation.captured_at,
            )
            if self.snapshot.phase is HumanFollowPhase.ACQUIRING:
                self._lifecycle.record_acquisition(self._assessment, now=now)
                if self.snapshot.phase is HumanFollowPhase.ACQUIRED:
                    remaining = (None if self.snapshot.mission_deadline is None
                                 else self.snapshot.mission_deadline - now)
                    distance = f"{self.request.stand_off_cm:g} centimètres"
                    text = (
                        f"Je vais suivre votre marqueur, à {distance}, "
                        f"pendant {self.request.duration_s:g} secondes."
                        if remaining is None else
                        f"Je reprends le suivi à {distance}. Il reste {remaining:g} secondes."
                    )
                    self._announce("activate" if remaining is None else "resume",
                                   text, remaining_s=remaining)
            elif self._assessment.status is not AcquisitionStatus.ACQUIRED:
                self.robot.suspend(self._assessment.reason.value)
                self._sync()
                self._write("suspended", reason=self._assessment.reason.value)
        if completed_announcement is not None:
            pending = self.pending_announcement
            if pending is None or pending.token != completed_announcement:
                self._write("announcement_completion_rejected", reason="obsolete_announcement")
                raise ProtectionFault("obsolete_announcement")
            if pending.template in {"activate", "resume"}:
                failures = self.conditions().failures()
                if failures:
                    self.robot.supervise(events=failures, defer_proof=True)
                    self._sync()
                    self._write("activation_refused", failures=failures)
                    return self.snapshot
            self.pending_announcement = None
            self._write("announcement_completed_by_adapter", token=pending.token)
            if pending.template in {"activate", "resume"}:
                deadline = (self.robot.time_fn() + self.request.duration_s
                            if self.snapshot.mission_deadline is None else None)
                self.robot.activate_human(self.permit, deadline=deadline)
                self._lifecycle.activate_after_announcement(
                    now=self.robot.time_fn(), mission_deadline=deadline,
                    conditions=self.conditions(),
                )
                self._write("activated")
        return self.snapshot

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
