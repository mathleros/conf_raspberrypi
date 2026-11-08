# Orchestration des skills du robot

Ce package regroupe la planification, l'exécution et le suivi des missions.

## Objectif

Le LLM ne doit pas piloter directement les GPIO. Sa fonction est plutôt :
- formuler l'intention,
- proposer un plan de haut niveau,
- transmettre une tâche structurée à l'orchestrateur,
- éviter les commandes non validées.

L'orchestrateur exécute un plan compilé, sans dépendance vers les interfaces
vocales, le LLM, les traces JSONL ou les pilotes matériels.

## Composants

### `SkillExecutor`

Exécute une `Skill` dans un `SkillContext` et renvoie un `SkillResult`.

### `SkillPlanner`
Décompose les intents composés en intents exécutables, puis compile chacun en
un `SkillPlanStep` qui associe l'intent à la séquence de skills enregistrées.
Le résultat est déterministe et ne laisse pas le LLM décider librement des actions.

### `MissionStateMachine`

Formalise les phases d'une mission :
- `idle`
- `planning`
- `executing`
- `success`
- `failed`
- `aborted`

### `MissionOrchestrator`

Possède la machine d'état et exécute les `SkillPlanStep` dans l'ordre :
retries, budgets par étape/mission et abandon à la première étape non terminée.
Un suivi continu n'a pas d'échéance et n'est pas relancé après erreur.
L'horloge monotone est injectable pour les tests. Entre deux mouvements en boucle ouverte
(`move_forward`, `move_backward`, `turn_left`, `turn_right`), l'orchestrateur attend
`motion_settle_seconds` pour laisser le châssis s'immobiliser ; cette pause est interruptible par un arrêt.

Les dépendances d'exécution sont passées à `execute` : fonction d'exécution d'une
étape, contrôle d'arrêt et observateur facultatif d'événements.
`CommandService` adapte ces événements en JSONL et garantit l'arrêt matériel
dans un `finally`. Une exception d'exécution marque la mission en échec et se
propage ; un plan vide est une erreur explicite.

Les délais ne préemptent pas une skill bloquante : ils sont vérifiés après
l'appel et entre étapes. Les contrôles d'urgence des skills/du robot restent
indispensables.

## Exemple d'utilisation

Le service d'application injecte ici le contrôleur déjà assemblé :

```python
from irobot.app.domain.intent import Intent
from irobot.app.domain.orchestrator import MissionOrchestrator, SkillPlanner

planner = SkillPlanner()
steps = planner.plan_intents([Intent(name="stop")])
mission = MissionOrchestrator()
try:
    results, status = mission.execute(
        steps,
        controller.handle_planned_step,
        stop_requested=robot.emergency_stop_requested,
    )
finally:
    robot.stop()
```
