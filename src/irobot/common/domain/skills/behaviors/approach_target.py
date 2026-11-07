from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from irobot.common.config.settings import RuntimeSettings
from irobot.common.domain.numbers import to_float
from irobot.common.domain.skills.base_skill import Skill, SkillContext, SkillResult
from irobot.common.domain.skills.behaviors.target_tracking import (
    Direction,
    OvershootRecovery,
    TargetTrackingMixin,
)

logger = logging.getLogger(__name__)


class ApproachTargetSkill(TargetTrackingMixin, Skill):
    """Behavior composite : rejoint une cible détectée jusqu'à la distance demandée.

    Ce behavior est un exemple de logique de niveau supérieur : il combine
    perception et primitives de déplacement.
    """

    name = "approach_target"
    description = "Rejoint une cible visuelle jusqu'à sa distance de consigne"

    DEFAULT_ALIGN_STEP_S = 0.08
    DEFAULT_FORWARD_STEP_S = 0.12
    DEFAULT_MAX_TRACKING_S = 8.0
    DEFAULT_MAX_TARGET_LOSS_S = 1.0
    MIN_FORWARD_SCALE = 0.25
    PHASE_SEARCH = "search"
    PHASE_TRACK = "track"

    def __init__(
        self,
        settings: RuntimeSettings | None = None,
        time_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self.time_fn = time_fn
        self.sleep_fn = sleep_fn

    def _resolve_stand_off_cm(self, params: dict[str, Any]) -> float:
        default_cm = float(self.settings.stand_off_default_cm)
        raw = params.get("approach_threshold_cm")
        if raw is None:
            raw = params.get("stand_off_cm")
        if raw is None:
            return default_cm
        value = to_float(raw, default_cm)
        low = float(self.settings.min_stand_off_cm)
        high = float(self.settings.max_stand_off_cm)
        return min(max(value, low), high)

    def _forward_step(self, base_step_s: float, distance_cm: float | None, stand_off_cm: float) -> float:
        # Impulsions raccourcies à l'approche pour ne pas dépasser le stand-off.
        if distance_cm is None or stand_off_cm <= 0.0 or distance_cm >= 2.0 * stand_off_cm:
            return base_step_s
        ratio = (distance_cm - stand_off_cm) / stand_off_cm
        return base_step_s * min(1.0, max(self.MIN_FORWARD_SCALE, ratio))

    def _halt(
        self,
        context: SkillContext,
        *,
        phase: str,
        message: str,
        data: dict[str, Any],
        confidence: float,
        status: str = "success",
        motion: str = "stop",
        **state: Any,
    ) -> SkillResult:
        self._stop_robot(context)
        context.state["motion"] = motion
        context.state["follow_target_state"] = {"phase": phase, **state}
        return SkillResult(
            status=status,
            message=message,
            data=data,
            confidence=confidence,
            next_action="stop_motion",
        )

    def _single_step(
        self,
        context: SkillContext,
        reached_threshold_cm: float,
        align_step_s: float,
        forward_step_s: float,
    ) -> SkillResult:
        """Mode sans perception live : un seul pas, l'appelant reboucle."""
        if self._check_obstacle_fail_safe(context):
            return self._halt(
                context,
                phase="blocked",
                message="Arrêt de sécurité : obstacle détecté pendant le suivi.",
                data={
                    "target_position": context.state.get("last_object_position"),
                    "obstacle_detected": True,
                    "obstacle_distance_cm": context.state.get("obstacle_distance_cm"),
                },
                confidence=0.99,
                iterations=1,
            )

        target_position, distance_cm = self._detect_target(context)
        offset_x = to_float(context.state.get("last_object_offset_x"))
        if distance_cm is not None and distance_cm <= reached_threshold_cm:
            context.state["close_enough"] = True
            return self._halt(
                context,
                phase="target_reached",
                message=f"Cible atteinte à {distance_cm:.1f} cm.",
                data={"target_position": target_position, "distance_cm": distance_cm, "close_enough": True},
                confidence=0.95,
                iterations=1,
                distance_cm=distance_cm,
            )

        if target_position is None:
            self._pulse_motion(context, "right", align_step_s)
            context.state["motion"] = "search_target"
            context.state["follow_target_state"] = {"phase": "searching", "iterations": 1}
            return SkillResult(
                status="in_progress",
                message="Cible non détectée : recherche active en rotation.",
                data={"target_position": None, "obstacle_detected": False},
                confidence=0.4,
                next_action="detect_object",
            )

        if self._needs_angular_correction(target_position, distance_cm, offset_x, reached_threshold_cm):
            direction = "left" if target_position == "left" else "right"
            self._pulse_motion(context, direction, align_step_s)
            context.state["motion"] = f"align_{direction}"
            context.state["follow_target_state"] = {"phase": "aligning", "direction": direction, "iterations": 1}
            return SkillResult(
                status="in_progress",
                message=f"Correction angulaire vers la {'gauche' if direction == 'left' else 'droite'}.",
                data={"target_position": target_position, "obstacle_detected": False},
                confidence=0.7,
                next_action="detect_object",
            )

        self._pulse_motion(context, "forward", forward_step_s)
        context.state["motion"] = "approach_target"
        context.state["follow_target_state"] = {"phase": "approaching", "iterations": 1, "distance_cm": distance_cm}
        return SkillResult(
            status="success",
            message="Approche de la cible en boucle fermée (itération).",
            data={"target_position": target_position, "obstacle_detected": False, "distance_cm": distance_cm},
            confidence=0.85,
            next_action="detect_object",
        )

    def _safety_halt(self, context: SkillContext, iterations: int) -> SkillResult | None:
        """Arrêt d'urgence d'abord, puis obstacle ; None si aucun des deux."""
        # Même convention que follow_object : arrêt d'urgence = "success" + data["emergency_stop"].
        if self._is_emergency_stop_requested(context):
            return self._halt(
                context,
                phase="blocked",
                message="Arrêt d'urgence demandé pendant le suivi.",
                data={"emergency_stop": True, "iterations": iterations},
                confidence=0.99,
                iterations=iterations,
                reason="emergency_stop",
            )

        if self._check_obstacle_fail_safe(context):
            return self._halt(
                context,
                phase="blocked",
                message="Arrêt de sécurité : obstacle détecté pendant le suivi.",
                data={
                    "target_position": context.state.get("last_object_position"),
                    "obstacle_detected": True,
                    "obstacle_distance_cm": context.state.get("obstacle_distance_cm"),
                },
                confidence=0.99,
                iterations=iterations,
                reason="obstacle_detected",
            )
        return None

    def _tracking_timeout_result(self, context: SkillContext, iterations: int, max_tracking_s: float) -> SkillResult:
        self._stop_robot(context)
        context.state["follow_target_state"] = {
            "phase": "tracking_timeout",
            "iterations": iterations,
            "timeout_s": max_tracking_s,
        }
        return SkillResult(
            status="in_progress",
            message="Suivi interrompu par timeout de tracking ; nouvelle acquisition requise.",
            data={
                "target_position": context.state.get("last_object_position"),
                "tracking_timeout": True,
                "iterations": iterations,
            },
            confidence=0.5,
            next_action="detect_object",
        )

    def _track_loop(
        self,
        context: SkillContext,
        *,
        max_tracking_s: float,
        max_target_loss_s: float,
        search_timeout_s: float,
        align_step_s: float,
        forward_step_s: float,
        stand_off_cm: float,
        reached_threshold_cm: float,
    ) -> SkillResult:
        """Mode perception live : boucle recherche / suivi jusqu'à atteinte, perte ou timeout."""
        now = self.time_fn
        tracking_started_at = now()
        phase = self.PHASE_SEARCH
        phase_since = tracking_started_at
        search_spent_s = 0.0
        last_seen_at: float | None = None
        sweep_direction: Direction = "right"
        recovery = OvershootRecovery(self.settings.target_recovery_attempts, self.ALIGN_SETTLE_S, self.RECOVERY_WINDOW_S)
        iterations = 0

        while True:
            searching_s = (now() - phase_since) if phase == self.PHASE_SEARCH else 0.0
            if (now() - tracking_started_at - search_spent_s - searching_s) > max(0.1, max_tracking_s):
                break
            iterations += 1

            halted = self._safety_halt(context, iterations)
            if halted is not None:
                return halted

            target_position, distance_cm = self._detect_target(context)
            offset_x = to_float(context.state.get("last_object_offset_x"))
            current = now()
            logger.info(
                "Suivi #%d phase=%s position=%s offset_x=%s distance=%s cached=%s",
                iterations,
                phase,
                target_position,
                offset_x,
                distance_cm,
                context.state.get("last_object_cached"),
            )

            if target_position is not None:
                if phase == self.PHASE_SEARCH:
                    search_spent_s += current - phase_since
                    phase = self.PHASE_TRACK
                last_seen_at = current
                if target_position in {"left", "right"}:
                    sweep_direction = target_position

                if distance_cm is not None and distance_cm <= reached_threshold_cm:
                    context.state["close_enough"] = True
                    return self._halt(
                        context,
                        phase="target_reached",
                        message=f"Cible atteinte à {distance_cm:.1f} cm.",
                        data={"target_position": target_position, "distance_cm": distance_cm, "close_enough": True},
                        confidence=0.95,
                        iterations=iterations,
                        distance_cm=distance_cm,
                    )

                if self._needs_angular_correction(target_position, distance_cm, offset_x, reached_threshold_cm):
                    logger.info("Suivi #%d décision : alignement %s (%.2f s)", iterations, target_position, align_step_s)
                    self._pulse_motion(context, target_position, align_step_s)
                    recovery.aligned(target_position, align_step_s, now())
                    context.state["motion"] = f"align_{target_position}"
                    context.state["follow_target_state"] = {
                        "phase": "aligning",
                        "direction": target_position,
                        "iterations": iterations,
                    }
                    self.sleep_fn(self.ALIGN_SETTLE_S)
                else:
                    step_s = self._forward_step(forward_step_s, distance_cm, stand_off_cm)
                    logger.info("Suivi #%d décision : avance (%.2f s)", iterations, step_s)
                    self._pulse_motion(context, "forward", step_s)
                    context.state["motion"] = "approach_target"
                    context.state["follow_target_state"] = {
                        "phase": "approaching",
                        "iterations": iterations,
                        "distance_cm": distance_cm,
                    }
                self.sleep_fn(self.CONTROL_LOOP_PERIOD_S)
                continue

            # Cible non visible
            if phase == self.PHASE_TRACK:
                reverse = None if context.state.get("last_object_cached") else recovery.reverse(current)
                if reverse is not None:
                    sweep_direction, step_s = reverse
                    self._sweep_step(context, sweep_direction, step_s, iterations)
                    continue
                lost_for_s = current - (last_seen_at if last_seen_at is not None else current)
                if lost_for_s < max(0.1, max_target_loss_s):
                    self._stop_robot(context)
                    context.state["motion"] = "search_target"
                    context.state["follow_target_state"] = {
                        "phase": "target_lost_grace",
                        "iterations": iterations,
                        "lost_for_s": round(lost_for_s, 3),
                    }
                    self.sleep_fn(self.CONTROL_LOOP_PERIOD_S)
                    continue
                phase = self.PHASE_SEARCH
                phase_since = current

            if (current - phase_since) >= max(0.1, search_timeout_s):
                return self._halt(
                    context,
                    phase="lost_target",
                    message="Cible introuvable : recherche épuisée, arrêt.",
                    data={"target_position": None, "obstacle_detected": False, "target_lost": True},
                    confidence=0.1,
                    status="failed",
                    motion="search_target",
                    iterations=iterations,
                    searched_for_s=round(current - phase_since, 3),
                )

            logger.info("Suivi #%d décision : balayage %s (cible non vue)", iterations, sweep_direction)
            self._sweep_step(context, sweep_direction, align_step_s, iterations)

        return self._tracking_timeout_result(context, iterations, max_tracking_s)

    def validate(self, context: SkillContext) -> bool:
        return context.robot is not None

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            if not hasattr(context.robot, "forward"):
                return SkillResult(
                    status="failed",
                    message="Le robot ne fournit pas de méthode forward() pour rejoindre la cible.",
                    data={"skill": self.name},
                    confidence=0.0,
                    next_action=None,
                )
            params = dict(context.state.get("active_intent_parameters") or {})
            max_tracking_s = to_float(params.get("tracking_timeout_s"), self.DEFAULT_MAX_TRACKING_S)
            max_target_loss_s = to_float(params.get("max_target_loss_s"), self.DEFAULT_MAX_TARGET_LOSS_S)
            align_step_s = to_float(params.get("alignment_step_s"), self.DEFAULT_ALIGN_STEP_S)
            forward_step_s = to_float(params.get("forward_step_s"), self.DEFAULT_FORWARD_STEP_S)
            search_timeout_s = to_float(
                params.get("search_timeout_s"),
                float(self.settings.search_timeout_seconds),
            )
            stand_off_cm = self._resolve_stand_off_cm(params)
            default_tolerance_cm = stand_off_cm * float(self.settings.stand_off_tolerance_percent) / 100.0
            tolerance_cm = max(
                0.0,
                to_float(params.get("stand_off_tolerance_cm"), default_tolerance_cm),
            )
            reached_threshold_cm = max(1.0, stand_off_cm + tolerance_cm)
            has_live_perception = callable(getattr(context.perception, "detect", None))

            if not has_live_perception:
                return self._single_step(context, reached_threshold_cm, align_step_s, forward_step_s)
            return self._track_loop(
                context,
                max_tracking_s=max_tracking_s,
                max_target_loss_s=max_target_loss_s,
                search_timeout_s=search_timeout_s,
                align_step_s=align_step_s,
                forward_step_s=forward_step_s,
                stand_off_cm=stand_off_cm,
                reached_threshold_cm=reached_threshold_cm,
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors de l'approche de la cible : {exc}",
                data={"error": str(exc), "skill": self.name},
                confidence=0.0,
                next_action=None,
            )
