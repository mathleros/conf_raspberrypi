from __future__ import annotations

import time
from typing import Any

from irobot.domain.skills.base_skill import Skill, SkillContext, SkillResult


class FollowTargetSkill(Skill):
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

    @staticmethod
    def _to_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_position(position: Any) -> str | None:
        if position is None:
            return None
        normalized = str(position).strip().lower()
        if normalized in {"center", "centre", "middle"}:
            return "center"
        if normalized in {"left", "right"}:
            return normalized
        if normalized in {"unknown", "none", ""}:
            return None
        return None

    def _check_obstacle_fail_safe(self, context: SkillContext) -> bool:
        if bool(context.state.get("obstacle_detected", False)):
            return True

        checker = getattr(context.robot, "check_obstacle", None)
        if checker is None:
            return False

        try:
            reading = checker()
        except Exception:
            return True

        if reading is None:
            return True
        return bool(reading)

    def _stop_robot(self, context: SkillContext) -> None:
        stop = getattr(context.robot, "stop", None)
        if callable(stop):
            stop()

    def _pulse_motion(self, context: SkillContext, direction: str, duration_s: float) -> None:
        duration = max(0.0, float(duration_s))
        directional_for = getattr(context.robot, f"{direction}_for", None)
        if callable(directional_for):
            directional_for(duration)
            return

        directional = getattr(context.robot, direction, None)
        if callable(directional):
            directional()
            if duration > 0.0:
                time.sleep(duration)

    def _detect_target(self, context: SkillContext) -> tuple[str | None, float | None]:
        params = dict(context.state.get("active_intent_parameters") or {})
        target_object = params.get("target_object") or context.state.get("target_object")
        detector = getattr(context.perception, "detect", None)

        if callable(detector):
            detection = detector(target=target_object)
            if detection is not None:
                context.state["target_object"] = getattr(detection, "label", target_object) or target_object
                context.state["last_object_position"] = getattr(detection, "position", None)
                context.state["last_object_distance_cm"] = getattr(detection, "distance_cm", None)

        position = self._normalize_position(
            context.state.get("last_object_position", context.state.get("last_ball_position"))
        )

        distance_raw = context.state.get("last_object_distance_cm")
        distance_cm: float | None
        try:
            distance_cm = float(distance_raw) if distance_raw is not None else None
        except (TypeError, ValueError):
            distance_cm = None
        return position, distance_cm

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
            approach_threshold_cm = self._to_float(
                params.get("approach_threshold_cm"),
                self.DEFAULT_APPROACH_THRESHOLD_CM,
            )
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
                if distance_cm is not None and distance_cm <= max(1.0, approach_threshold_cm):
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

            tracking_started_at = time.monotonic()
            last_seen_at = tracking_started_at
            iterations = 0

            while (time.monotonic() - tracking_started_at) <= max(0.1, max_tracking_s):
                iterations += 1

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
                if target_position is not None:
                    last_seen_at = time.monotonic()

                if distance_cm is not None and distance_cm <= max(1.0, approach_threshold_cm):
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

                if target_position is None:
                    if (time.monotonic() - last_seen_at) >= max(0.1, max_target_loss_s):
                        self._stop_robot(context)
                        context.state["motion"] = "search_target"
                        context.state["follow_target_state"] = {
                            "phase": "lost_target",
                            "iterations": iterations,
                            "lost_for_s": round(time.monotonic() - last_seen_at, 3),
                        }
                        return SkillResult(
                            status="failed",
                            message="Perte prolongée de la cible : arrêt du suivi.",
                            data={"target_position": None, "obstacle_detected": False, "target_lost": True},
                            confidence=0.1,
                            next_action="stop_motion",
                        )

                    self._pulse_motion(context, "right", align_step_s)
                    context.state["motion"] = "search_target"
                    context.state["follow_target_state"] = {
                        "phase": "searching",
                        "iterations": iterations,
                    }
                    time.sleep(self.CONTROL_LOOP_PERIOD_S)
                    continue

                if target_position == "left":
                    self._pulse_motion(context, "left", align_step_s)
                    context.state["motion"] = "align_left"
                    context.state["follow_target_state"] = {
                        "phase": "aligning",
                        "direction": "left",
                        "iterations": iterations,
                    }
                    time.sleep(self.CONTROL_LOOP_PERIOD_S)
                    continue

                if target_position == "right":
                    self._pulse_motion(context, "right", align_step_s)
                    context.state["motion"] = "align_right"
                    context.state["follow_target_state"] = {
                        "phase": "aligning",
                        "direction": "right",
                        "iterations": iterations,
                    }
                    time.sleep(self.CONTROL_LOOP_PERIOD_S)
                    continue

                self._pulse_motion(context, "forward", forward_step_s)
                context.state["motion"] = "follow_target"
                context.state["follow_target_state"] = {
                    "phase": "approaching",
                    "iterations": iterations,
                    "distance_cm": distance_cm,
                }
                time.sleep(self.CONTROL_LOOP_PERIOD_S)

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
