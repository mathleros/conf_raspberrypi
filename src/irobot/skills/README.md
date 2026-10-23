# Skills du robot

Ce package contient les compétences unitaires du robot, structurées selon un
contrat commun.

## Contrat de base

Chaque skill doit dériver de `Skill` et implémenter :
- `execute(context) -> SkillResult`
- éventuellement `validate(context) -> bool`

Les résultats sont homogènes et ne doivent jamais dépendre d'un texte libre
improvisé. Cela permet à un orchestrateur de décider de manière fiable de la
suite à exécuter.

## Skills disponibles

- `MoveForwardSkill`
- `TurnLeftSkill`
- `TurnRightSkill`
- `StopMotionSkill`
- `DetectRedBallSkill`
- `DetectObstacleSkill`
- `FollowTargetSkill`
- `MoveCircleSkill`

## Schéma de résultat

```python
SkillResult(
    status="success",
    message="...",
    data={...},
    confidence=0.9,
    next_action="skill_name",
)
```

## Principes de conception

- une skill doit être testable indépendamment ;
- une skill ne doit pas savoir comment le LLM a formulé la demande ;
- une skill doit retourner un résultat standardisé ;
- les conditions de sécurité doivent être prises en compte dans le flux de
  validation ou dans l'orchestrateur ;
- les skills doivent rester petites et spécialisées.

## Exemple d'utilisation

```python
from irobot.skills import MoveForwardSkill, SkillContext

context = SkillContext(robot=car, state={})
skill = MoveForwardSkill()
result = skill.execute(context)
print(result)
```
