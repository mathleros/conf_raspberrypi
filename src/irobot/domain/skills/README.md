# Skills du robot

Ce package regroupe les compétences exécutables du robot selon un contrat
commun (`Skill`, `SkillContext`, `SkillResult`).

## Contrat

Chaque skill implémente :
- `execute(context) -> SkillResult`
- optionnellement `validate(context) -> bool`

Les skills n'accèdent pas directement aux GPIO ; elles passent par
`RobotController` injecté dans le contexte.

## Organisation

### Primitives
- `MoveForwardSkill`
- `MoveBackwardSkill`
- `TurnLeftSkill`
- `TurnRightSkill`
- `StopMotionSkill`

### Perception
- `DetectObjectSkill`
- `DetectObstacleSkill`

### Behaviors composites
- `FollowTargetSkill`
- `MoveCircleSkill`

## Note importante sur `MoveCircleSkill`

`MoveCircleSkill` est un behavior composite, pas une primitive.
Il doit être interprété comme une séquence de primitives (rotation + avance)
pilotée par l'orchestrateur.

Exemple logique de plan :

```python
plan = [
  ("turn_left", 0.5),
  ("move_forward", 0.2),
  ("turn_left", 0.5),
  ("move_forward", 0.2),
  ("stop_motion", None),
]
```

## Exemple de résultat

```python
SkillResult(
  status="success",
  message="...",
  data={...},
  confidence=0.9,
  next_action="skill_name",
)
```
