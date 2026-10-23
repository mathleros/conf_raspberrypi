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

## Adapter matériel / skills

Les skills n'interagissent pas directement avec les GPIO ni avec la classe
concrète `SmartCar2WD`.

Elles utilisent le contexte partagé qui contient un adaptateur :
- `RobotController`

Exemple de contexte :

```python
from irobot.robot_controller import RobotController
from irobot.skills import SkillContext
from irobot.smart_car.smart_car import SmartCar2WD

car = SmartCar2WD()
context = SkillContext(
    robot=RobotController(car),
    state={},
)
```

Dans ce schéma, la skill appelle :
- `context.robot.forward()`
- `context.robot.left()`
- `context.robot.stop()`

et non pas directement les broches GPIO.

## Hiérarchie recommandée des skills

### 1. Skills primitives (atomiques)

Ce sont les actions de base du robot :

- `MoveForwardSkill`
- `MoveBackwardSkill`
- `TurnLeftSkill`
- `TurnRightSkill`
- `StopMotionSkill`

Ces skills doivent être simples, deterministes et sécurisées.

### 2. Skills de perception

- `DetectRedBallSkill`
- `DetectObstacleSkill`

### 3. Behaviors / tâches composites

Ce sont des séquences de skills primitives, généralement orchestration + observation + boucle de contrôle :

- `FollowTargetSkill`
- `MoveCircleSkill`

Important : `MoveCircleSkill` ne doit pas être considéré comme une primitive. Il s'agit d'une composition de mouvements, typiquement :

- `turn_left` pendant X secondes
- éventuellement `move_forward` pendant un petit intervalle pour tracer un arc
- `stop_motion` quand le cercle est terminé

## Skills disponibles

- `MoveForwardSkill`
- `MoveBackwardSkill`
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
from irobot.robot_controller import RobotController
from irobot.skills import MoveForwardSkill, SkillContext
from irobot.smart_car.smart_car import SmartCar2WD

car = SmartCar2WD()
context = SkillContext(robot=RobotController(car), state={})
skill = MoveForwardSkill()
result = skill.execute(context)
print(result)
```
