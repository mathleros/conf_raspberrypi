# Guide de Correction Rétroactif — Audit V2 : Priorité P2 (Lissage du Suivi Visuel)

**Origine :** Audit Architecture & Qualité V2  
**Gravité :** Mécanique & Dynamique (P2)  
**Fichier cible :** `src/irobot/domain/skills/behaviors/follow_target.py`  
**Objectif :** Supprimer les arrêts intempestifs `stop()` après chaque micro-impulsion dans la méthode `_pulse_motion()`.

---

## 1. Description du Problème

Dans la version V2, `_pulse_motion()` appelait `directional()`, temporisait brièvement, puis appelait systématiquement `self._stop_robot(context)`. Cela générait un mouvement de type "staccato" très saccadé (à-coups de 0.12s suivis d'arrêts complets), secouant le châssis et déstabilisant la caméra.

---

## 2. Code à Modifier

Dans `src/irobot/domain/skills/behaviors/follow_target.py` :

```python
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
[-]         self._stop_robot(context) # Supprimé pour éviter de stopper net les moteurs
```

---

## 3. Comment Tester ?

Vérifiez que le test unitaire de suivi s'exécute sans interruption :
```bash
uv run pytest tests/unit/test_skills_behaviors.py -k "test_follow_target_skill_success_when_target_visible"
```
*Résultat attendu :* Le statut est `success` et la commande `forward` est envoyée en continu.
