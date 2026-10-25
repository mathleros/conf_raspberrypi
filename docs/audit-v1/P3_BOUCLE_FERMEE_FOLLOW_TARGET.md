# Guide de Correction Rétroactif — Audit V1 : Priorité P3 (Boucle Fermée FollowTarget)

**Origine :** Audit Architecture & Qualité V1  
**Gravité :** Fonctionnel & Autonomie (P3)  
**Fichier cible :** `src/irobot/domain/skills/behaviors/follow_target.py`  
**Objectif :** Remplacer le comportement one-shot par une boucle d'asservissement continu avec gestion de perte de cible et seuil d'approche.

---

## 1. Description du Problème

Initialement, `FollowTargetSkill.execute()` lisait la position de la balle une seule fois dans `context.state`, avançait d'un coup, puis terminait immédiatement. Le robot n'était pas capable de poursuivre une balle en mouvement ni de corriger son orientation en continu.

---

## 2. Code à Modifier

Dans `src/irobot/domain/skills/behaviors/follow_target.py`, implémentation de la boucle fermée conditionnée par la présence d'un flux de perception en direct :

```python
class FollowTargetSkill(Skill):
    name = "follow_target"
    description = "Suit une cible visuelle et applique des garde-fous"

[+] CONTROL_LOOP_PERIOD_S = 0.02
[+] DEFAULT_ALIGN_STEP_S = 0.08
[+] DEFAULT_FORWARD_STEP_S = 0.12
[+] DEFAULT_MAX_TRACKING_S = 8.0
[+] DEFAULT_MAX_TARGET_LOSS_S = 1.0

    def execute(self, context: SkillContext) -> SkillResult:
        ...
[+]     has_live_perception = callable(getattr(context.perception, "detect", None))

        # Si perception live disponible : boucle d'asservissement continue
[+]     if has_live_perception:
[+]         tracking_started_at = time.monotonic()
[+]         last_seen_at = tracking_started_at
[+]         while (time.monotonic() - tracking_started_at) <= max_tracking_s:
[+]             if self._check_obstacle_fail_safe(context):
[+]                 self._stop_robot(context)
[+]                 return SkillResult(status="success", message="Arrêt obstacle", next_action="stop_motion")
[+]             target_position, distance_cm = self._detect_target(context)
[+]             if target_position is not None:
[+]                 last_seen_at = time.monotonic()
[+]             if distance_cm and distance_cm <= approach_threshold_cm:
[+]                 return SkillResult(status="success", message="Cible atteinte", next_action="stop_motion")
[+]             if target_position is None and (time.monotonic() - last_seen_at) >= max_target_loss_s:
[+]                 return SkillResult(status="failed", message="Perte de cible", next_action="stop_motion")
[+]             if target_position == "left":
[+]                 self._pulse_motion(context, "left", align_step_s)
[+]             elif target_position == "right":
[+]                 self._pulse_motion(context, "right", align_step_s)
[+]             else:
[+]                 self._pulse_motion(context, "forward", forward_step_s)
[+]             time.sleep(self.CONTROL_LOOP_PERIOD_S)
```

---

## 3. Comment Tester ?

Exécutez le test simulant la visibilité continue d'une cible :
```bash
uv run pytest tests/unit/test_skills_behaviors.py
```
*Résultat attendu :* Le statut renvoie `success` et la commande `forward` est bien transmise au robot.
