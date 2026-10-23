# Structure du package `irobot`

Cette organisation vise à rendre visible la hiérarchie fonctionnelle du robot :

```text
src/irobot/
├── README.md
├── __init__.py
├── robot_controller.py
├── camera/
├── sensors/
├── smart_car/
├── voice_assistant/
├── skills/
│   ├── __init__.py
│   ├── base_skill.py
│   ├── primitives/
│   │   ├── __init__.py
│   │   ├── move_forward.py
│   │   ├── move_backward.py
│   │   ├── turn_left.py
│   │   ├── turn_right.py
│   │   └── stop_motion.py
│   ├── perception/
│   │   ├── __init__.py
│   │   ├── detect_red_ball.py
│   │   └── detect_obstacle.py
│   └── behaviors/
│       ├── __init__.py
│       ├── follow_target.py
│       └── move_circle.py
├── orchestrator/
│   ├── __init__.py
│   ├── executor.py
│   ├── planner.py
│   ├── mission_state_machine.py
│   └── README.md
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
