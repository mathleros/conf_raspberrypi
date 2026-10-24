# Orchestration des skills du robot

Ce package formalise une première couche d'orchestration pour le robot.

## Objectif

Le LLM ne doit pas piloter directement les GPIO. Sa fonction est plutôt :
- formuler l'intention,
- proposer un plan de haut niveau,
- transmettre une tâche structurée à l'orchestrateur,
- éviter les commandes non validées.

L'orchestrateur, lui, exécutera des `Skill` selon un contrat standardisé.

## Composants

### `SkillExecutor`

Exécute une `Skill` dans un `SkillContext` et renvoie un `SkillResult`.

### `SkillPlanner`

Organise les skills selon l'intention reçue. À ce stade, il est un planificateur simple et explicite.

### `MissionStateMachine`

Formalise les phases d'une mission :
- `idle`
- `planning`
- `executing`
- `success`
- `failed`
- `aborted`

## Exemple d'utilisation

```python
from irobot.skills import DetectObjectSkill, FollowTargetSkill, StopMotionSkill
from irobot.orchestrator import SkillExecutor, SkillPlanner, MissionStateMachine
from irobot.skills.base_skill import SkillContext

context = SkillContext(
    robot=robot,
    state={"camera_ready": True, "last_ball_position": "centre"},
)

executor = SkillExecutor(context)
planner = SkillPlanner([DetectObjectSkill(), FollowTargetSkill(), StopMotionSkill()])
mission = MissionStateMachine()

mission.start("follow_red_ball", target="red_ball")
mission.begin_execution()

for skill in planner.plan("follow_red_ball"):
    result = executor.run(skill)
    print(result)
```

## Prochaine évolution recommandée

- validation stricte du plan produit par le LLM,
- machine d'états plus avancée avec transitions explicites,
- garde-fou de sécurité par obstacle,
- boucle de contrôle de suivi visuel,
- temps d'exécution, timeout et retry sur erreur.
