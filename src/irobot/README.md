# Structure du package `irobot`

Cette organisation vise à rendre visible la hiérarchie fonctionnelle du robot :

```text
src/irobot/
├── README.md
├── __init__.py
├── domain/
│   ├── orchestrator/
│   └── skills/
│       ├── base_skill.py
│       ├── primitives/
│       │   ├── move_forward.py
│       │   ├── move_backward.py
│       │   ├── turn_left.py
│       │   ├── turn_right.py
│       │   └── stop_motion.py
│       ├── perception/
│       │   ├── detect_object.py
│       │   └── detect_obstacle.py
│       └── behaviors/
│           ├── follow_target.py
│           └── move_circle.py
├── interfaces/
├── hardware/
└── ...
```

## Règle de conception

- `skills/primitives` : actions atomiques du robot
- `skills/perception` : lecture de capteurs et perception visuelle
- `skills/behaviors` : comportements / tâches composites
- `orchestrator` : planification, exécution et supervision

La séparation est conçue pour refléter la bonne pratique suivante :
- le LLM produit une intention de haut niveau ;
- l'orchestrateur la transforme en plan ;
- le plan est décomposé en skills primitives ;
- les skills primitives pilotent le robot via `RobotController`.
