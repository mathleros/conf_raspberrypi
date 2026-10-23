from __future__ import annotations

from irobot.skills.base_skill import Skill, SkillContext, SkillResult


class DetectRedBallSkill(Skill):
    """Détecte une balle rouge dans le champ visuel.

    Cette version sert de squelette d'architecture. La logique métier exacte
    sera branchée sur le module `color_detector.py` ou un wrapper dédié.
    """

    name = "detect_red_ball"
    description = "Retourne la position de la balle rouge si elle est visible"

    def validate(self, context: SkillContext) -> bool:
        return context.camera is not None or context.state.get("camera_ready") is True

    def execute(self, context: SkillContext) -> SkillResult:
        try:
            # Ici, la logique concrète peut appeler le détecteur OpenCV ou un
            # service visuel. Ce squelette retourne une structure explicite.
            position = context.state.get("last_ball_position", "UNKNOWN")

            if position == "UNKNOWN":
                return SkillResult(
                    status="failed",
                    message="Aucune balle rouge détectée.",
                    data={"position": None},
                    confidence=0.0,
                    next_action="scan_for_target",
                )

            return SkillResult(
                status="success",
                message="Balle rouge détectée.",
                data={"position": position},
                confidence=0.8,
                next_action="align_to_target",
            )
        except Exception as exc:  # pragma: no cover - logique métier
            return SkillResult(
                status="failed",
                message=f"Erreur lors de la détection : {exc}",
                data={"error": str(exc)},
                confidence=0.0,
                next_action=None,
            )
