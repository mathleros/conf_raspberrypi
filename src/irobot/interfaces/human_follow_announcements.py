"""Announcement preparation, explicit completion and suspension wording."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from irobot.interfaces.protection import ProtectionFault

if TYPE_CHECKING:
    from irobot.interfaces.human_follow_runtime import HumanFollowRuntime


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


def invalidate(runtime: HumanFollowRuntime) -> None:
    previous = runtime.pending_announcement
    runtime.pending_announcement = None
    if previous is not None:
        runtime._write("announcement_invalidated", token=previous.token)


def announce(
    runtime: HumanFollowRuntime, template: str, text: str, *,
    remaining_s: float | None = None,
) -> None:
    runtime._invalidate_announcement()
    context = runtime.snapshot.context
    if context is None:
        raise ProtectionFault("no_human_context")
    runtime._announcement_sequence += 1
    now = runtime.robot.time_fn()
    runtime.pending_announcement = HumanAnnouncement(
        f"{context.mission_id}:{context.context_version}:{runtime._announcement_sequence}",
        context.mission_id, context.context_version, template, text,
        now, now + runtime._announcement_timeout, remaining_s,
    )
    runtime._write("announcement_prepared", template=template,
                   token=runtime.pending_announcement.token, remaining_s=remaining_s)


def announce_acquired(runtime: HumanFollowRuntime, now: float) -> None:
    remaining = (None if runtime.snapshot.mission_deadline is None
                 else runtime.snapshot.mission_deadline - now)
    distance = f"{runtime.request.stand_off_cm:g} centimètres"
    text = (
        f"Je vais suivre votre marqueur, à {distance}, "
        f"pendant {runtime.request.duration_s:g} secondes."
        if remaining is None else
        f"Je reprends le suivi à {distance}. Il reste {remaining:g} secondes."
    )
    runtime._announce("activate" if remaining is None else "resume", text, remaining_s=remaining)


def complete(runtime: HumanFollowRuntime, completed_announcement: str) -> None:
    pending = runtime.pending_announcement
    if pending is None or pending.token != completed_announcement:
        runtime._write("announcement_completion_rejected", reason="obsolete_announcement")
        raise ProtectionFault("obsolete_announcement")
    if pending.template in {"activate", "resume"}:
        failures = runtime.conditions().failures()
        if failures:
            runtime.robot.supervise(events=failures, defer_proof=True)
            runtime._sync()
            runtime._write("activation_refused", failures=failures)
            return
    runtime.pending_announcement = None
    runtime._write("announcement_completed_by_adapter", token=pending.token)
    if pending.template in {"activate", "resume"}:
        deadline = (runtime.robot.time_fn() + runtime.request.duration_s
                    if runtime.snapshot.mission_deadline is None else None)
        try:
            runtime.robot.activate_human(runtime.permit, deadline=deadline)
        except ProtectionFault as exc:
            runtime.robot.suspend(str(exc))
            runtime._sync()
            raise
        runtime._lifecycle.activate_after_announcement(
            now=runtime.robot.time_fn(), mission_deadline=deadline,
            conditions=runtime.conditions(),
        )
        runtime._write("activated")


def suspension_text(runtime: HumanFollowRuntime) -> str:
    messages = {
        "observation_absent": ("Marqueur perdu", "Rendez votre marqueur visible."),
        "observation_ambiguous": (
            "Identifiant attendu en plusieurs exemplaires",
            "Ne laissez visible qu'un exemplaire du marqueur configuré.",
        ),
        "stale": ("Image périmée", "Rétablissez la caméra."),
        "observations_fresh": ("Image périmée", "Rétablissez la caméra."),
        "stream_changed": ("Flux renouvelé", "Vérifiez le flux de perception."),
        "perception_fault": ("Perception indisponible", "Rétablissez le flux de perception."),
        "obstacle": ("Obstacle détecté", "Dégagez l'obstacle."),
        "obstacle_clear": ("Obstacle détecté", "Dégagez l'obstacle."),
        "output_audio_ready": ("Sortie audio défaillante", "Rétablissez l'audio."),
        "input_audio_ready": ("Entrée audio défaillante", "Rétablissez l'audio."),
    }
    cause = runtime.robot.causes[0] if runtime.robot.causes else ""
    reason, correction = messages.get(cause, ("Défaut signalé", "Vérifiez le défaut signalé."))
    return f"{reason}, suivi suspendu. {correction} Dites : reprends le suivi."
