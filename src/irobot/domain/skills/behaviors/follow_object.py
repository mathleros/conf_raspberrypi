from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable

from irobot.config.settings import RuntimeSettings
from irobot.domain.numbers import to_float
from irobot.domain.skills.base_skill import Skill, SkillContext, SkillResult
from irobot.domain.skills.behaviors.target_tracking import Direction, TargetTrackingMixin


class FollowObjectSkill(TargetTrackingMixin, Skill):
    """Suit une cible jusqu'à un arrêt, ou pendant une durée explicitement demandée."""

    name = "follow_object"
    description = "Suit une cible visuelle à distance constante jusqu'à un arrêt"

    DEFAULT_TARGET = "yellow"
    DEFAULT_STAND_OFF_CM = 100.0
    DEFAULT_TOLERANCE_CM = 15.0
    DEFAULT_DURATION_S = 60.0
    DEFAULT_MAX_TARGET_LOSS_S = 3.0
    ALIGN_STEP_S = 0.08
    FORWARD_MIN_S = 0.05
    FORWARD_MAX_S = 0.25
    BACKWARD_MIN_S = 0.05
    BACKWARD_MAX_S = 0.15

    def __init__(
        self,
        settings: RuntimeSettings | None = None,
        time_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self.time_fn = time_fn
        self.sleep_fn = sleep_fn

    def validate(self, context: SkillContext) -> bool:
        return context.robot is not None

    def _step(self, gap_cm: float, low_s: float, high_s: float, *, backward: bool = False) -> float:
        # Durée proportionnelle à l'écart, à la vitesse linéaire calibrée.
        calibrated_speed = self.settings.cm_per_second
        if backward and self.settings.backward_cm_per_second is not None:
            calibrated_speed = self.settings.backward_cm_per_second
        speed = max(1.0, float(calibrated_speed))
        return min(high_s, max(low_s, gap_cm / speed))

    def _result(
        self,
        status: str,
        message: str,
        data: dict,
        confidence: float,
    ) -> SkillResult:
        return SkillResult(
            status=status,
            message=message,
            data=data,
            confidence=confidence,
            next_action="stop_motion" if status == "success" else None,
        )

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            return self._run(context)
        except Exception as exc:
            return SkillResult(
                status="failed",
                message=f"Erreur lors du suivi d'objet : {exc}",
                data={"error": str(exc), "skill": self.name},
                confidence=0.0,
                next_action=None,
            )
        finally:
            try:
                self._stop_robot(context)
            except Exception:
                logging.getLogger(__name__).exception("Impossible d'arreter le robot apres le suivi")

    def _run(self, context: SkillContext) -> SkillResult:
        params = dict(context.state.get("active_intent_parameters") or {})
        settings = self.settings
        if not callable(getattr(context.perception, "detect", None)):
            raise RuntimeError("Le suivi nécessite une perception visuelle active")
        if not params.get("target_object"):
            params["target_object"] = self.DEFAULT_TARGET
            context.state["active_intent_parameters"] = params

        approach_follow = context.state.get("active_intent_name") in {"follow_person", "follow_red_ball"}
        default_stand_off_cm = 20.0 if approach_follow else self.DEFAULT_STAND_OFF_CM
        default_tolerance_cm = 10.0 if approach_follow else self.DEFAULT_TOLERANCE_CM
        stand_off_cm = default_stand_off_cm if params.get("stand_off_cm") is None else min(
            max(to_float(params.get("stand_off_cm"), default_stand_off_cm), float(settings.min_stand_off_cm)),
            float(settings.max_stand_off_cm),
        )
        tolerance_cm = max(0.0, to_float(params.get("stand_off_tolerance_cm"), default_tolerance_cm))
        continuous = params.get("duration_s") is None
        duration_s = math.inf if continuous else min(
            max(0.0, to_float(params.get("duration_s"), self.DEFAULT_DURATION_S)),
            float(settings.max_follow_duration_sec),
        )
        max_loss_s = max(0.0, to_float(params.get("max_target_loss_s"), self.DEFAULT_MAX_TARGET_LOSS_S))
        search_timeout_s = max(
            0.1, to_float(params.get("search_timeout_s"), float(settings.search_timeout_seconds))
        )

        now = self.time_fn
        started_at = now()
        last_seen_at = started_at
        search_started_at: float | None = None
        sweep_direction: Direction = "right"
        iterations = 0
        reacquisitions = 0
        final_distance_cm: float | None = None

        def set_state(phase: str, **extra) -> None:
            context.state["follow_target_state"] = {"phase": phase, "iterations": iterations, **extra}

        while now() - started_at < duration_s:
            iterations += 1

            emergency = self._is_emergency_stop_requested(context)
            if emergency or self._check_obstacle_fail_safe(context):
                self._stop_robot(context)
                context.state["motion"] = "stop"
                set_state("blocked", reason="emergency_stop" if emergency else "obstacle_detected")
                data = {"obstacle_detected": True, "iterations": iterations, "final_distance_cm": final_distance_cm}
                if emergency:
                    data["emergency_stop"] = True
                return self._result("success", "Arrêt de sécurité pendant le suivi.", data, 0.99)

            position, distance_cm = self._detect_target(context)
            current = now()

            if position is None:
                self._stop_robot(context)
                if current - last_seen_at < max_loss_s:
                    context.state["motion"] = "search_target"
                    set_state("searching", lost_for_s=round(current - last_seen_at, 3))
                    self.sleep_fn(self.CONTROL_LOOP_PERIOD_S)
                    continue
                if search_started_at is None:
                    search_started_at = current
                if not continuous and current - search_started_at >= search_timeout_s:
                    set_state("lost_target", searched_for_s=round(current - search_started_at, 3))
                    return self._result(
                        "failed",
                        "Cible introuvable : recherche épuisée, arrêt.",
                        {
                            "target_lost": True,
                            "iterations": iterations,
                            "reacquisitions": reacquisitions,
                            "final_distance_cm": final_distance_cm,
                        },
                        0.1,
                    )
                self._sweep_step(context, sweep_direction, self.ALIGN_STEP_S, iterations)
                continue

            if search_started_at is not None:
                reacquisitions += 1
                search_started_at = None
            last_seen_at = current
            if distance_cm is not None:
                final_distance_cm = distance_cm

            if position in {"left", "right"}:
                sweep_direction = position
                self._pulse_motion(context, position, self.ALIGN_STEP_S)
                context.state["motion"] = f"align_{position}"
                set_state("aligning", direction=position)
            elif distance_cm is not None and distance_cm > stand_off_cm + tolerance_cm:
                self._pulse_motion(
                    context, "forward", self._step(distance_cm - stand_off_cm, self.FORWARD_MIN_S, self.FORWARD_MAX_S)
                )
                context.state["motion"] = "follow_object"
                set_state("approaching", distance_cm=distance_cm)
            elif not approach_follow and distance_cm is not None and distance_cm < stand_off_cm - tolerance_cm:
                self._pulse_motion(
                    context, "backward",
                    self._step(stand_off_cm - distance_cm, self.BACKWARD_MIN_S, self.BACKWARD_MAX_S, backward=True),
                )
                context.state["motion"] = "follow_object"
                set_state("backing", distance_cm=distance_cm)
            else:
                self._stop_robot(context)
                context.state["motion"] = "stop"
                set_state("holding", distance_cm=distance_cm)
            self.sleep_fn(self.CONTROL_LOOP_PERIOD_S)

        self._stop_robot(context)
        context.state["motion"] = "stop"
        return self._result(
            "success",
            f"Suivi terminé après {duration_s:.0f} s.",
            {
                "iterations": iterations,
                "duration_s": duration_s,
                "final_distance_cm": final_distance_cm,
                "reacquisitions": reacquisitions,
            },
            0.9,
        )
