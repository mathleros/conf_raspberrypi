# Guide de Correction Rétroactif — Audit V1 : Priorité P4 (Factorisation DRY & BlackboardState)

**Origine :** Audit Architecture & Qualité V1  
**Gravité :** Maintenabilité & Typage (P4)  
**Fichiers cibles :** 
- `src/irobot/domain/skills/primitives/base_motion_primitive.py` (création)
- `src/irobot/domain/skills/blackboard_state.py` (création)
- `src/irobot/hardware/audio/audio_utils.py` (création)

**Objectif :** Supprimer la duplication massive des primitives de mouvement et typer les variables partagées dans le contexte d'exécution.

---

## 1. Description du Problème

1. `MoveForwardSkill`, `MoveBackwardSkill`, `TurnLeftSkill` et `TurnRightSkill` partageaient 90 % de code dupliqué (extraction de paramètres `distance`, `side`, `unit`, `duration` et conversions).
2. Le contexte `SkillContext.state` utilisait un dictionnaire brut non typé `dict[str, Any]` avec des clés arbitraires (`last_ball_position` vs `last_object_position`).
3. Les utilitaires ALSA / Bluetooth étaient dupliqués à l'identique entre `voice_assistant.py` et `voice_runtime.py`.

---

## 2. Code à Modifier

### Étape A : Création de `BaseMotionPrimitiveSkill`
Création du fichier `src/irobot/domain/skills/primitives/base_motion_primitive.py` factorisant la logique de mouvement :

```python
[+] class BaseMotionPrimitiveSkill(Skill):
[+]     motion: str = "motion"
[+]     command_method: str = ""
[+]     command_for_method: str = ""
[+]     parameter_mode: str = "distance"  # distance|angle
[+]     ...
[+]     def execute(self, context: SkillContext) -> SkillResult:
[+]         payload = self._resolve_motion_parameters(context)
[+]         duration = payload.get("duration")
[+]         if not self._execute_motion(context, duration):
[+]             return SkillResult(status="failed", message=self.failure_message)
[+]         context.state["motion"] = self.motion
[+]         return SkillResult(status="success", data={"motion": self.motion, **payload})
```

Les classes dérivées deviennent de simples déclarations :
```python
# move_forward.py
[u] class MoveForwardSkill(BaseMotionPrimitiveSkill):
[u]     name = "move_forward"
[u]     motion = "forward"
[u]     command_method = "forward"
[u]     command_for_method = "forward_for"
```

### Étape B : Création de `BlackboardState`
Création de `src/irobot/domain/skills/blackboard_state.py` implémentant `MutableMapping[str, Any]` avec `KNOWN_FIELDS` :

```python
[+] @dataclass
[+] class BlackboardState(MutableMapping[str, Any]):
[+]     active_intent: Any | None = None
[+]     target_object: str | None = None
[+]     last_object_position: str | None = None
[+]     last_object_distance_cm: float | None = None
[+]     obstacle_detected: bool = False
[+]     close_enough: bool = False
[+]     extra: dict[str, Any] = field(default_factory=dict)
```

---

## 3. Comment Tester ?

Vérifiez que toutes les primitives de mouvement et de perception continuent de passer :
```bash
uv run pytest tests/unit/test_skills_primitives.py
uv run pytest tests/unit/test_skills_perception.py
```
*Résultat attendu :* 100 % des tests unitaires au vert.
