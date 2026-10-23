# MoveCircleSkill : comportement composite, pas primitive

## Rôle

`MoveCircleSkill` représente un comportement de haut niveau qui doit être décomposé en plusieurs actions de base du robot.

Il ne s'agit pas d'une primitive atomique comme `turn_left` ou `move_forward`.

## Exemple de réalisation logique

Pour faire un cercle, l'orchestrateur peut utiliser une séquence de type :

1. `TurnLeftSkill` pendant 0.6 s
2. `MoveForwardSkill` pendant 0.2 s
3. répéter tant que la durée totale n'est pas atteinte
4. `StopMotionSkill` à la fin

Autre variante :

- tourner en permanence vers la gauche tout en avançant légèrement
- calculer la durée ou la distance parcourue
- arrêter à la fin

## Idée de conception

Le robot ne doit pas décider de manière libre :
- “je vais faire un rond”

Il doit plutôt exécuter une séquence validée par un plan calculé :

```python
plan = [
    ("turn_left", 0.5),
    ("move_forward", 0.2),
    ("turn_left", 0.5),
    ("move_forward", 0.2),
]
```

## Conclusion

- `turn_left` et `move_forward` sont des skills primitives.
- `move_circle` est un behavior composite.
- le LLM doit générer un plan ou une intention de haut niveau ;
- l'orchestrateur transforme cette intention en primitives.
