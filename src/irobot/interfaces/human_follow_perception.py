"""Frame processing and acquisition decisions on the runtime's single session state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from irobot.interfaces.human_lifecycle import HumanFollowPhase
from irobot.interfaces.human_perception import (
    AcquisitionAssessment, AcquisitionReason, AcquisitionStatus,
    HumanMarkerAcquisition, HumanMarkerMissionContext, HumanPerceptionFrame, HumanPerceptionProvider,
    HumanPerceptionStreamFault, MarkerObservation, ObservationDisposition,
)
from irobot.interfaces.protection import ProtectionFault

if TYPE_CHECKING:
    from irobot.interfaces.human_follow_runtime import HumanFollowRuntime


def _context_is_current(
    runtime: HumanFollowRuntime, context: HumanMarkerMissionContext, *, event: str,
    acquisition: HumanMarkerAcquisition | None = None,
) -> bool:
    runtime.robot.supervise(defer_proof=True)
    runtime._sync()
    if (runtime.snapshot.context != context
            or runtime.snapshot.phase is HumanFollowPhase.SUSPENDED
            or (acquisition is not None and acquisition is not runtime._acquisition)):
        runtime._write(
            event, reason="obsolete_context",
            requested_mission=context.mission_id, requested_context=context.context_version,
        )
        return False
    return True


def _read_observation(
    runtime: HumanFollowRuntime, frame: HumanPerceptionFrame | None,
    provider: HumanPerceptionProvider | None, context: HumanMarkerMissionContext,
) -> tuple[
    HumanPerceptionFrame | None, MarkerObservation | None, HumanPerceptionStreamFault | None,
] | None:
    try:
        if runtime._frame_source is not None:
            frame = runtime._frame_source.read_frame()
            provider = runtime._provider
    except HumanPerceptionStreamFault as exc:
        return frame, None, exc
    except Exception:
        _perception_exception(runtime)
        raise
    if not isinstance(frame, HumanPerceptionFrame):
        raise TypeError("Frame source must return a HumanPerceptionFrame")
    if not _context_is_current(runtime, context, event="perception_input_discarded"):
        return None
    if runtime._wait_expired(runtime.robot.time_fn()):
        return None
    if provider is None:
        raise ProtectionFault("no_human_perception_provider")
    try:
        return frame, provider.observe(frame, context=context), None
    except HumanPerceptionStreamFault as exc:
        return frame, None, exc
    except Exception:
        _perception_exception(runtime)
        raise


def _perception_exception(runtime: HumanFollowRuntime) -> None:
    try:
        runtime.robot.priority_one("human_perception_exception")
    finally:
        runtime.terminate("human_perception_exception")


def process_frame(
    runtime: HumanFollowRuntime, frame: HumanPerceptionFrame | None,
    provider: HumanPerceptionProvider | None,
) -> tuple[MarkerObservation, AcquisitionAssessment, float] | None:
    context = runtime.snapshot.context
    acquisition = runtime._acquisition
    if context is None or acquisition is None:
        raise ProtectionFault("no_human_acquisition")
    result = _read_observation(runtime, frame, provider, context)
    if result is None:
        return None
    frame, observation, fault = result
    # Results produced in flight cannot override a stop, deadline or new context.
    if not _context_is_current(
        runtime, context, event="perception_result_discarded", acquisition=acquisition,
    ):
        return None
    now = runtime.robot.time_fn()
    if runtime._wait_expired(now):
        return None
    if fault is not None:
        acquisition.reset()
        runtime._assessment = AcquisitionAssessment(
            AcquisitionStatus.REJECTED, AcquisitionReason.PERCEPTION_FAULT, 0,
            detail=str(fault),
        )
        runtime._observation = None
        runtime._write("perception_fault", reason=str(fault))
        if runtime.snapshot.phase is HumanFollowPhase.ACQUIRING:
            runtime._lifecycle.record_acquisition(runtime._assessment, now=now)
        else:
            runtime.robot.suspend(AcquisitionReason.PERCEPTION_FAULT.value)
            runtime._sync()
        return None
    if not isinstance(frame, HumanPerceptionFrame):
        raise TypeError("Frame source must return a HumanPerceptionFrame")
    if not isinstance(observation, MarkerObservation):
        acquisition.reset()
        raise TypeError("Human provider must return a MarkerObservation")
    return observation, acquisition.observe_frame(frame, observation, now=now), now


def _assess_stream(
    runtime: HumanFollowRuntime, observation: MarkerObservation,
    assessment: AcquisitionAssessment,
) -> AcquisitionAssessment:
    acquisition = runtime._acquisition
    if acquisition is None:
        raise ProtectionFault("no_human_acquisition")
    stream = (observation.source_id, observation.stream_generation)
    if stream in runtime._retired_streams:
        acquisition.reset()
        assessment = AcquisitionAssessment(
            AcquisitionStatus.REJECTED, AcquisitionReason.STREAM_CHANGED, 0,
            detail="obsolete_stream",
        )
    elif assessment.reason is AcquisitionReason.STREAM_CHANGED:
        if runtime._last_stream is not None:
            runtime._retired_streams.add(runtime._last_stream)
        runtime._last_stream = stream
    elif assessment.status is not AcquisitionStatus.REJECTED:
        if runtime._last_stream is not None and runtime._last_stream != stream:
            runtime._retired_streams.add(runtime._last_stream)
            if runtime.snapshot.mission_deadline is None:
                acquisition.reset()
                assessment = AcquisitionAssessment(
                    AcquisitionStatus.REJECTED, AcquisitionReason.STREAM_CHANGED, 0,
                    detail="stream_changed_after_fault",
                )
        runtime._last_stream = stream
    if (assessment.status is not AcquisitionStatus.REJECTED
            and observation.captured_at < runtime._context_started_at):
        acquisition.reset()
        assessment = AcquisitionAssessment(
            AcquisitionStatus.REJECTED, AcquisitionReason.CONTEXT_MISMATCH, 0,
            detail="capture_precedes_context",
        )
    return assessment


def accept_observation(
    runtime: HumanFollowRuntime, observation: MarkerObservation, *,
    assessed: AcquisitionAssessment | None, now: float,
) -> None:
    if runtime._acquisition is None or runtime.snapshot.context is None:
        raise ProtectionFault("no_human_acquisition")
    if not isinstance(observation, MarkerObservation):
        raise TypeError("Human runtime requires a structured marker observation")
    if not isinstance(observation.disposition, ObservationDisposition):
        runtime._acquisition.reset()
        raise ValueError("Human runtime requires a typed observation disposition")
    assessment = (
        assessed if assessed is not None
        else runtime._acquisition.observe(observation, now=now)
    )
    assessment = _assess_stream(runtime, observation, assessment)
    runtime._assessment = assessment
    runtime._observation = observation
    runtime._write(
        "observation_assessed", reason=assessment.reason.value,
        confirmations=assessment.confirmations, detail=assessment.detail,
        disposition=observation.disposition.value,
        frame=observation.frame_number, captured_at=observation.captured_at,
        published_at=observation.published_at,
        source=observation.source_id, stream=observation.stream_generation,
        calibration=observation.calibration_version,
        identity_matches=observation.identity == runtime.snapshot.context.identity,
        robot_clearance_cm=observation.robot_clearance_cm,
        optical_distance_cm=observation.optical_distance_cm,
        age_s=now - observation.captured_at,
    )
    if assessment.reason is AcquisitionReason.STREAM_CHANGED:
        runtime.robot.suspend(assessment.reason.value)
        runtime._sync()
    elif runtime.snapshot.phase is HumanFollowPhase.ACQUIRING:
        runtime._lifecycle.record_acquisition(assessment, now=now)
        if runtime.snapshot.phase is HumanFollowPhase.ACQUIRED:
            runtime._announce_acquired(now)
    elif assessment.status is not AcquisitionStatus.ACQUIRED:
        runtime.robot.suspend(assessment.reason.value)
        runtime._sync()
        runtime._write("suspended", reason=assessment.reason.value)
