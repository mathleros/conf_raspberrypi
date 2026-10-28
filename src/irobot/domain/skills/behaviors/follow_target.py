from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from irobot.config.settings import RuntimeSettings, load_runtime_settings
from irobot.domain.skills.base_skill import Skill, SkillContext, SkillResult
from irobot.domain.skills.behaviors.target_tracking import TargetTrackingMixin


class FollowTargetSkill(TargetTrackingMixin, Skill):
    """Behavior composite : suit une cible détectée.

    Ce behavior est un exemple de logique de niveau supérieur : il combine
    perception et primitives de déplacement.
    """

    name = "follow_target"
    description = "Suit une cible visuelle et applique des garde-fous"

    CONTROL_LOOP_PERIOD_S = 0.02
    DEFAULT_ALIGN_STEP_S = 0.08
    DEFAULT_FORWARD_STEP_S = 0.12
    DEFAULT_MAX_TRACKING_S = 8.0
    DEFAULT_MAX_TARGET_LOSS_S = 1.0
    DEFAULT_APPROACH_THRESHOLD_CM = 20.0
    DEFAULT_STAND_OFF_TOLERANCE_CM = 10.0
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

    @property
    def settings(self) -> RuntimeSettings:
        if self._settings is None:
            self._settings = load_runtime_settings()
        return self._settings

    def _resolve_stand_off_cm(self, params: dict[str, Any]) -> float:
        raw = params.get("approach_threshold_cm")
        if raw is None:
            raw = params.get("stand_off_cm")
        if raw is None:
            return self.DEFAULT_APPROACH_THRESHOLD_CM
        value = self._to_float(raw, self.DEFAULT_APPROACH_THRESHOLD_CM)
        low = float(self.settings.min_stand_off_cm)
        high = float(self.settings.max_stand_off_cm)
        return min(max(value, low), high)

    def _forward_step(self, base_step_s: float, distance_cm: float | None, stand_off_cm: float) -> float:
        # Impulsions raccourcies à l'approche pour ne pas dépasser le stand-off.
        if distance_cm is None or stand_off_cm <= 0.0 or distance_cm >= 2.0 * stand_off_cm:
            return base_step_s
        ratio = (distance_cm - stand_off_cm) / stand_off_cm
        return base_step_s * min(1.0, max(self.MIN_FORWARD_SCALE, ratio))

    def validate(self, context: SkillContext) -> bool:
        return context.robot is not None

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            if not hasattr(context.robot, "forward"):
                return SkillResult(
                    status="failed",
                    message="Le robot ne fournit pas de méthode forward() pour suivre la cible.",
                    data={"skill": self.name},
                    confidence=0.0,
                    next_action=None,
                )

            params = dict(context.state.get("active_intent_parameters") or {})
            max_tracking_s = self._to_float(params.get("tracking_timeout_s"), self.DEFAULT_MAX_TRACKING_S)
            max_target_loss_s = self._to_float(params.get("max_target_loss_s"), self.DEFAULT_MAX_TARGET_LOSS_S)
            align_step_s = self._to_float(params.get("alignment_step_s"), self.DEFAULT_ALIGN_STEP_S)
            forward_step_s = self._to_float(params.get("forward_step_s"), self.DEFAULT_FORWARD_STEP_S)
            search_timeout_s = self._to_float(
                params.get("search_timeout_s"),
                float(self.settings.search_timeout_seconds),
            )
            stand_off_cm = self._resolve_stand_off_cm(params)
            tolerance_cm = max(
                0.0,
                self._to_float(params.get("stand_off_tolerance_cm"), self.DEFAULT_STAND_OFF_TOLERANCE_CM),
            )
            reached_threshold_cm = max(1.0, stand_off_cm + tolerance_cm)
            has_live_perception = callable(getattr(context.perception, "detect", None))

            if not has_live_perception:
                if self._check_obstacle_fail_safe(context):
                    self._stop_robot(context)
                    context.state["motion"] = "stop"
                    context.state["follow_target_state"] = {"phase": "blocked", "iterations": 1}
                    return SkillResult(
                        status="success",
                        message="Arrêt de sécurité : obstacle détecté pendant le suivi.",
                        data={"target_position": context.state.get("last_object_position"), "obstacle_detected": True},
                        confidence=0.99,
                        next_action="stop_motion",
                    )

                target_position, distance_cm = self._detect_target(context)
                if distance_cm is not None and distance_cm <= reached_threshold_cm:
                    self._stop_robot(context)
                    context.state["motion"] = "stop"
                    context.state["close_enough"] = True
                    context.state["follow_target_state"] = {
                        "phase": "target_reached",
                        "iterations": 1,
                        "distance_cm": distance_cm,
                    }
                    return SkillResult(
                        status="success",
                        message=f"Cible atteinte à {distance_cm:.1f} cm.",
                        data={"target_position": target_position, "distance_cm": distance_cm, "close_enough": True},
                        confidence=0.95,
                        next_action="stop_motion",
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

                if target_position == "left":
                    self._pulse_motion(context, "left", align_step_s)
                    context.state["motion"] = "align_left"
                    context.state["follow_target_state"] = {
                        "phase": "aligning",
                        "direction": "left",
                        "iterations": 1,
                    }
                    return SkillResult(
                        status="in_progress",
                        message="Correction angulaire vers la gauche.",
                        data={"target_position": target_position, "obstacle_detected": False},
                        confidence=0.7,
                        next_action="detect_object",
                    )

                if target_position == "right":
                    self._pulse_motion(context, "right", align_step_s)
                    context.state["motion"] = "align_right"
                    context.state["follow_target_state"] = {
                        "phase": "aligning",
                        "direction": "right",
                        "iterations": 1,
                    }
                    return SkillResult(
                        status="in_progress",
                        message="Correction angulaire vers la droite.",
                        data={"target_position": target_position, "obstacle_detected": False},
                        confidence=0.7,
                        next_action="detect_object",
                    )

                self._pulse_motion(context, "forward", forward_step_s)
                context.state["motion"] = "follow_target"
                context.state["follow_target_state"] = {
                    "phase": "approaching",
                    "iterations": 1,
                    "distance_cm": distance_cm,
                }
                return SkillResult(
                    status="success",
                    message="Suivi de la cible en boucle fermée (itération).",
                    data={"target_position": target_position, "obstacle_detected": False, "distance_cm": distance_cm},
                    confidence=0.85,
                    next_action="detect_object",
                )

            now = self.time_fn
            tracking_started_at = now()
            phase = self.PHASE_SEARCH
            phase_since = tracking_started_at
            search_spent_s = 0.0
            last_seen_at: float | None = None
            sweep_direction = "right"
            iterations = 0

            while True:
                searching_s = (now() - phase_since) if phase == self.PHASE_SEARCH else 0.0
                if (now() - tracking_started_at - search_spent_s - searching_s) > max(0.1, max_tracking_s):
                    break
                iterations += 1

                # Même convention que follow_object : arrêt d'urgence = "success" + data["emergency_stop"].
                if self._is_emergency_stop_requested(context):
                    self._stop_robot(context)
                    context.state["motion"] = "stop"
                    context.state["follow_target_state"] = {
                        "phase": "blocked",
                        "iterations": iterations,
                        "reason": "emergency_stop",
                    }
                    return SkillResult(
                        status="success",
                        message="Arrêt d'urgence demandé pendant le suivi.",
                        data={"emergency_stop": True, "iterations": iterations},
                        confidence=0.99,
                        next_action="stop_motion",
                    )

                if self._check_obstacle_fail_safe(context):
                    self._stop_robot(context)
                    context.state["motion"] = "stop"
                    context.state["follow_target_state"] = {
                        "phase": "blocked",
                        "iterations": iterations,
                        "reason": "obstacle_detected",
                    }
                    return SkillResult(
                        status="success",
                        message="Arrêt de sécurité : obstacle détecté pendant le suivi.",
                        data={"target_position": context.state.get("last_object_position"), "obstacle_detected": True},
                        confidence=0.99,
                        next_action="stop_motion",
                    )

                target_position, distance_cm = self._detect_target(context)
                current = now()

                if target_position is not None:
                    if phase == self.PHASE_SEARCH:
                        search_spent_s += current - phase_since
                        phase = self.PHASE_TRACK
                    last_seen_at = current
                    if target_position in {"left", "right"}:
                        sweep_direction = target_position

                    if distance_cm is not None and distance_cm <= reached_threshold_cm:
                        self._stop_robot(context)
                        context.state["motion"] = "stop"
                        context.state["close_enough"] = True
                        context.state["follow_target_state"] = {
                            "phase": "target_reached",
                            "iterations": iterations,
                            "distance_cm": distance_cm,
                        }
                        return SkillResult(
                            status="success",
                            message=f"Cible atteinte à {distance_cm:.1f} cm.",
                            data={
                                "target_position": target_position,
                                "distance_cm": distance_cm,
                                "close_enough": True,
                            },
                            confidence=0.95,
                            next_action="stop_motion",
                        )

                    if target_position in {"left", "right"}:
                        self._pulse_motion(context, target_position, align_step_s)
                        context.state["motion"] = f"align_{target_position}"
                        context.state["follow_target_state"] = {
                            "phase": "aligning",
                            "direction": target_position,
                            "iterations": iterations,
                        }
                    else:
                        step_s = self._forward_step(forward_step_s, distance_cm, stand_off_cm)
                        self._pulse_motion(context, "forward", step_s)
                        context.state["motion"] = "follow_target"
                        context.state["follow_target_state"] = {
                            "phase": "approaching",
                            "iterations": iterations,
                            "distance_cm": distance_cm,
                        }
                    self.sleep_fn(self.CONTROL_LOOP_PERIOD_S)
                    continue

                # Cible non visible
                if phase == self.PHASE_TRACK:
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
                    self._stop_robot(context)
                    context.state["motion"] = "search_target"
                    context.state["follow_target_state"] = {
                        "phase": "lost_target",
                        "iterations": iterations,
                        "searched_for_s": round(current - phase_since, 3),
                    }
                    return SkillResult(
                        status="failed",
                        message="Cible introuvable : recherche épuisée, arrêt.",
                        data={"target_position": None, "obstacle_detected": False, "target_lost": True},
                        confidence=0.1,
                        next_action="stop_motion",
                    )

                self._sweep_step(context, sweep_direction, align_step_s, iterations)

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
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors du suivi de cible : {exc}",
                data={"error": str(exc), "skill": self.name},
                confidence=0.0,
                next_action=None,
            )
