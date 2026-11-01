"""Protected admission, supervision and structured human sessions."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from irobot.interfaces.human_follow_runtime import (
    HumanAnnouncement,
    HumanFollowRequest,
    HumanFollowRuntime,
)
from irobot.interfaces.human_lifecycle import HumanFollowSnapshot
from irobot.interfaces.human_perception import (
    HumanPerceptionFrame,
    HumanPerceptionFrameSource,
    HumanPerceptionProvider,
    MarkerObservation,
)
from irobot.interfaces.plan_guards import is_pure_stop, fold, follow_request_refusal
from irobot.interfaces.protection import (
    AdmissionRequest,
    DecisionJournal,
    HumanConditions,
    MissionPermit,
    ProtectionFault,
)
from irobot.interfaces.robot_controller import RobotController
from irobot.domain.orchestrator.executor import SkillExecutor
from irobot.domain.skills.base_skill import Skill, SkillContext
from irobot.interfaces.voice_constants import HUMAN_RESUME_COMMANDS
from irobot.interfaces.voice_state import VoiceRuntimeState


class VoiceProtectionMixin(VoiceRuntimeState):
    def handle_text_as_plan(self, text: str, *, admission_request: AdmissionRequest | None = None):
        if self._protected() and admission_request is None:
            admission_request = self.robot.capture_admission_request()
        if is_pure_stop(text):
            return self._handle_stop_plan(text)
        if " ".join(fold(text).split()) in HUMAN_RESUME_COMMANDS:
            return self._resume_reserved_skill()
        refusal = follow_request_refusal(text)
        if refusal:
            return {"status": "rejected", "reason": refusal}
        if self._protected() and self.robot.reservation is not None:
            if self._worker_owns_supervision():
                return {"status": "rejected", "reason": "mission_reserved"}
            self.supervise_once()
            if self.robot.reservation is not None:
                return {"status": "rejected", "reason": "mission_reserved"}
        if not self._admission_lock.acquire(blocking=False):
            return {"status": "rejected", "reason": "mission_reserved"}
        try:
            if self._protected():
                self.robot.clear_emergency_stop()
                self._active_permit = self.robot.admit(request=admission_request)
            return self._handle_text_as_plan(text)
        except ProtectionFault as exc:
            return {"status": "aborted", "reason": "protection_fault", "causes": (str(exc),)}
        except Exception:
            if self._protected():
                self.robot.priority_one("runtime_exception")
            raise
        finally:
            try:
                if self._active_permit is not None:
                    self.robot.finish(self._active_permit)
            except Exception:
                self.robot.priority_one("runtime_cleanup_exception")
                raise
            finally:
                self._active_permit = None
                self._admission_lock.release()

    def _handle_stop_plan(self, text: str) -> dict[str, Any]:
        if self._human_follow is not None:
            self._request_emergency_stop()
            return self.advance_human_follow(events=("stop",))
        if self._protected():
            human = self.robot.reservation is not None and self.robot.reservation.human
            self._request_emergency_stop()
            if self._worker_owns_supervision():
                return {"status": "stop_requested", "source": "local_stop"}
        if self._protected() and self.robot.reservation is not None:
            self.supervise_once(events=("stop",))
            reservation = self.robot.reservation
            if reservation is not None:
                self.robot.finish(reservation.permit)
            self._reserved_skill = None
            self._reserved_context = None
            self._reserved_context_key = None
            if human:
                return {"status": "stopped", "source": "local_stop", "steps": []}
        return self._handle_text_as_plan(text)

    def _protected(self) -> bool:
        return isinstance(self.robot, RobotController) and self.robot.protection_present

    @property
    def human_follow_snapshot(self) -> HumanFollowSnapshot | None:
        return self._human_follow.snapshot if self._human_follow is not None else None

    @property
    def pending_human_announcement(self) -> HumanAnnouncement | None:
        return self._human_follow.pending_announcement if self._human_follow is not None else None

    def prepare_human_follow(
        self, request: HumanFollowRequest, *,
        conditions: Callable[[], HumanConditions], journal: DecisionJournal,
        max_age_seconds: float | None = None,
        announcement_timeout_seconds: float | None = None,
        frame_source: HumanPerceptionFrameSource | None = None,
        provider: HumanPerceptionProvider | None = None,
    ) -> dict[str, Any]:
        """Structured integration seam only; never selected by text, LLM or live assembly."""
        if not self._protected():
            return {"status": "rejected", "reason": "human_capability_unavailable"}
        if self.threaded:
            return {"status": "rejected", "reason": "human_preparation_requires_synchronous_runtime"}
        if not self._admission_lock.acquire(blocking=False):
            return {"status": "rejected", "reason": "mission_reserved"}
        try:
            if self.robot.reservation is not None:
                return {"status": "rejected", "reason": "mission_reserved"}
            self.robot.clear_emergency_stop()
            self._human_follow = HumanFollowRuntime(
                self.robot, self.settings, request, conditions, journal,
                max_age_seconds=max_age_seconds,
                announcement_timeout_seconds=announcement_timeout_seconds,
                frame_source=frame_source, provider=provider,
            )
            snapshot = self._human_follow.cycle()
            if snapshot.context is None:
                raise ProtectionFault("+".join(self.robot.causes))
            return {"status": snapshot.phase.value, "snapshot": snapshot,
                    **self._human_follow.result_metadata()}
        except ProtectionFault as exc:
            return {"status": "rejected", "reason": str(exc)}
        except Exception:
            if self._human_follow is not None:
                try:
                    self.robot.priority_one("human_runtime_exception")
                finally:
                    self._human_follow.terminate("human_runtime_exception")
            raise
        finally:
            if self._human_follow is not None and self._human_follow.snapshot.context is None:
                self._human_follow = None
            self._admission_lock.release()

    def advance_human_follow(
        self, *, events: tuple[str, ...] = (),
        observation: MarkerObservation | None = None,
        frame: HumanPerceptionFrame | None = None,
        provider: HumanPerceptionProvider | None = None,
        completed_announcement: str | None = None,
        holding: bool | None = None,
    ) -> dict[str, Any]:
        if self._human_follow is None:
            return {"status": "rejected", "reason": "no_human_session"}
        if holding is not None and not isinstance(holding, bool):
            raise TypeError("Human hold request must be a boolean")
        if self._worker_owns_supervision() or not self._admission_lock.acquire(blocking=False):
            return {"status": "rejected", "reason": "mission_reserved"}
        try:
            snapshot = self._human_follow.cycle(
                events=events, observation=observation, frame=frame, provider=provider,
                completed_announcement=completed_announcement,
            )
            if holding is True:
                snapshot = self._human_follow.hold()
            elif holding is False:
                snapshot = self._human_follow.continue_tracking()
            return {"status": snapshot.phase.value, "snapshot": snapshot,
                    "causes": self.robot.causes, **self._human_follow.result_metadata()}
        except ProtectionFault as exc:
            return {"status": "rejected", "reason": str(exc), "causes": self.robot.causes,
                    **self._human_follow.result_metadata()}
        except Exception:
            try:
                self.robot.priority_one("human_runtime_exception")
            finally:
                self._human_follow.terminate("human_runtime_exception")
            raise
        finally:
            if self._human_follow.snapshot.context is None:
                self._human_follow = None
            self._admission_lock.release()

    def _worker_owns_supervision(self) -> bool:
        return (self._worker is not None and self._worker.is_alive()
                and self._worker is not threading.current_thread())

    def supervise_once(self, *, events: tuple[str, ...] = ()) -> None:
        """One evaluated cycle, including idle. Never a standalone heartbeat."""
        if self._protected():
            if self._worker_owns_supervision():
                raise ProtectionFault("supervision_owned_by_worker")
            if self._human_follow is not None:
                result = self.advance_human_follow(events=events)
                if result["status"] == "rejected":
                    raise ProtectionFault(result["reason"])
                return
            self.robot.supervise(events=events)
            reservation = self.robot.reservation
            if reservation is not None and reservation.phase in {"locked", "ended"}:
                self.mission.abort("+".join(self.robot.causes))
                self.robot.finish(reservation.permit)
                self._reserved_skill = None
                self._reserved_context = None
                self._reserved_context_key = None

    def run_supervised(
        self, read_request: Callable[[], str | None], continue_running: Callable[[], bool],
    ) -> None:
        """Synchronous monitored loop with an injected non-live request source.

        A blocked request/evaluation/mission prevents completion and thus renewal.
        There is deliberately no independent proof thread.
        """
        if not self._protected() or self.threaded:
            raise ValueError("Supervised loop requires protected synchronous runtime")
        try:
            while continue_running():
                request = read_request()
                if request is not None:
                    self.last_result = self.handle_text_as_plan(request)
                self.supervise_once()
                self.robot.sleep_fn(self.robot.CONTROL_LOOP_PERIOD_S)
        except Exception:
            self.robot.priority_one("supervised_loop_exception")
            raise
        finally:
            self.robot.stop()

    def execute_reserved_skill(self, permit: MissionPermit, skill: Skill) -> dict[str, Any]:
        """Infrastructure seam for isolated mission providers, not a language route."""
        if self._human_follow is not None:
            return {"status": "rejected", "reason": "human_motion_provider_unavailable"}
        if not self._protected():
            return {"status": "rejected", "reason": "invalid_reservation"}
        if not self._admission_lock.acquire(blocking=False):
            return {"status": "rejected", "reason": "mission_reserved"}
        initial = self.robot.reservation
        metadata = {
            "mission": permit.mission, "context": permit.context, "armament": permit.armament,
            "mission_deadline": initial.deadline if initial is not None else None,
        }
        try:
            return self._run_reserved_skill(permit, skill, metadata)
        except ProtectionFault as exc:
            reservation = self.robot.reservation
            if reservation is not None and reservation.phase == "suspended":
                return {"status": "suspended", "reason": str(exc), "causes": self.robot.causes,
                        "required_action": "correct_faults_then_explicit_resume", **metadata}
            return {"status": "aborted", "reason": "protection_fault", "causes": self.robot.causes,
                    "reason_detail": str(exc),
                    "required_action": ("manual_rearm_then_new_request"
                                        if reservation is not None and reservation.phase == "locked"
                                        else "new_request"), **metadata}
        except Exception:
            self.robot.priority_one("mission_exception")
            raise
        finally:
            try:
                self.robot.stop()
                reservation = self.robot.reservation
                if (reservation is not None and reservation.permit == permit
                        and reservation.phase != "suspended"):
                    self.robot.finish(permit)
                    self._reserved_skill = None
                    self._reserved_context = None
                    self._reserved_context_key = None
            except Exception:
                self.robot.priority_one("runtime_cleanup_exception")
                raise
            finally:
                self._admission_lock.release()

    def _run_reserved_skill(
        self, permit: MissionPermit, skill: Skill, metadata: dict[str, Any],
    ) -> dict[str, Any]:
        self.robot.supervise()
        if not self.robot.valid_result(permit):
            raise ProtectionFault("+".join(self.robot.causes or ("obsolete_context",)))
        self._reserved_skill = skill
        key = (permit.generation, permit.mission)
        context = self._reserved_context
        if context is None or self._reserved_context_key != key:
            context = SkillContext()
            self._reserved_context = context
            self._reserved_context_key = key
        context.robot = self.robot.bind(permit)
        result = SkillExecutor(context).run(skill)
        self.robot.supervise()
        reservation = self.robot.reservation
        if reservation is None or reservation.permit != permit:
            return {"status": "aborted", "reason": "obsolete_result",
                    "required_action": "new_request", **metadata}
        if reservation.phase == "suspended":
            return {"status": "suspended", "causes": self.robot.causes,
                    "required_action": "correct_faults_then_explicit_resume", **metadata}
        if reservation.phase != "active":
            return {"status": "aborted", "reason": "protection_fault", "causes": self.robot.causes,
                    "required_action": ("manual_rearm_then_new_request"
                                        if reservation.phase == "locked" else "new_request"),
                    **metadata}
        return {"status": result.status, "results": [result]}

    def _resume_reserved_skill(self) -> dict[str, Any]:
        if self._worker_owns_supervision():
            return {"status": "rejected", "reason": "mission_reserved"}
        if self._human_follow is not None:
            if not self._admission_lock.acquire(blocking=False):
                return {"status": "rejected", "reason": "mission_reserved"}
            try:
                snapshot = self._human_follow.resume()
                return {"status": snapshot.phase.value, "snapshot": snapshot,
                        "causes": self.robot.causes, **self._human_follow.result_metadata()}
            except ProtectionFault as exc:
                return {"status": "rejected", "reason": str(exc)}
            except Exception:
                try:
                    self.robot.priority_one("human_resume_exception")
                finally:
                    self._human_follow.terminate("human_resume_exception")
                raise
            finally:
                if self._human_follow.snapshot.context is None:
                    self._human_follow = None
                self._admission_lock.release()
        if not self._protected() or self._reserved_skill is None:
            return {"status": "rejected", "reason": "no_resumable_session"}
        try:
            permit = self.robot.resume()
        except ProtectionFault as exc:
            reservation = self.robot.reservation
            if reservation is not None and reservation.phase in {"locked", "ended"}:
                self.robot.finish(reservation.permit)
                self._reserved_skill = None
                self._reserved_context = None
                self._reserved_context_key = None
            return {"status": "rejected", "reason": str(exc)}
        return self.execute_reserved_skill(permit, self._reserved_skill)
