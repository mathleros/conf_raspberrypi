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
│           ├── approach_target.py
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

Le LLM produit une intention de haut niveau ; l'orchestrateur la transforme en
plan de skills primitives, qui pilotent le robot via `RobotController`.
Le LLM n'est jamais un pilote matériel.

## Organisation du runtime vocal

Le point d'entrée public reste [interfaces/voice_runtime.py](interfaces/voice_runtime.py)
(`voice-runtime`, `VoiceRuntime`, fonctions LLM et `build_hardware_runtime`).

| Module | Responsabilité |
| --- | --- |
| `interfaces/voice_state.py` | État partagé, configuration, annulation, contrôleur et écriture JSONL |
| `interfaces/voice_constants.py` | Vocabulaire et valeurs par défaut des plans |
| `interfaces/voice_llm_transport.py` | Prompts, HTTP, formats de réponse, métriques et cache |
| `interfaces/voice_llm.py` | Reconstruction des intentions, grounding, repli local et préchauffage |
| `interfaces/voice_plan.py` | Normalisation, bornage, expansion et validation déterministes |
| `interfaces/voice_execution.py` | Séquence de mission, retries, délais et traces d'exécution |
| `hardware/audio/voice_input.py` | Capture ALSA, nettoyage du processus et transcription Vosk |
| `hardware/voice_runtime_factory.py` | Assemblage moteur/capteur/caméra sur Raspberry Pi |

Les deux mixins de planification et d'exécution utilisent un unique état partagé.
Les anciens modules de protection, d'admission et de suivi humain ne sont plus
requis. Les adaptateurs matériels sont importés uniquement lors de leur utilisation :
charger le runtime ou traiter du texte n'initialise ni ALSA, ni Vosk, ni GPIO, ni caméra.

La perception caméra attend une image traitée pour la cible demandée au démarrage
et lors d'un changement de cible (par exemple balle rouge vers marqueur avec
« suis-moi »). Une image encore en traitement pour l'ancienne cible ne satisfait
pas cette attente, limitée à une seconde et interrompue à la fermeture ou en cas
d'échec caméra. Un dépassement est journalisé et ne fournit aucune détection.
Le suivi ArUco conserve l'arrêt sur absence ou perte du marqueur, sans balayage.
Une protection déclarée `present` reste refusée, faute d'adaptateur qualifié.

La distance ArUco du runtime et du diagnostic utilise la même fonction
[estimate_marker_distance_cm](hardware/camera/distance_estimator.py) : pose
`solvePnP` à partir des quatre coins, puis distance directe objectif–centre
du marqueur. L'inclinaison et le décentrage sont pris en compte. Le carré est
supposé mesurer 8 cm ; la focale provisoire est 600 px pour l'image tournée
480×640, avec centre optique centré et distorsion nulle. Sans calibration
optique, la précision réelle, notamment aux bords, reste à vérifier sur le Pi.
Une pose inexploitable est journalisée et ne fournit aucune détection, sans
repli sur la largeur apparente. L'estimation des balles, les seuils de position
et l'absence de fusion ultrason pour les marqueurs restent inchangés.

Dans `handle_transcript()`, toute occurrence du mot `stop`, `arrête`, `halte` ou
`pause` (accents, casse et ponctuation normalisés) entraîne immédiatement
`robot.stop()` puis la demande d'arrêt d'urgence, avant tout appel au parseur,
au LLM ou à la perception. Cela vaut aussi sans mission active et dans une
phrase contenant d'autres commandes. La mission est marquée `aborted` ;
le signal d'annulation interdit les retries et les étapes suivantes, même si
la planification LLM est encore en cours. Une nouvelle commande ne peut effacer
ce signal qu'une fois le worker précédent terminé.
L'entrée directe `handle_text_as_plan()` et l'écoute continue utilisent le même
chemin de planification ; la priorité lexicale des arrêts s'applique à
`handle_transcript()`.

## Organisation du contrôleur robot

[RobotController](interfaces/robot_controller.py) adapte le pilote injecté :
mouvements, vitesse, ultrason et arrêt d'urgence logiciel. Aucun mode protégé,
permis de mission ou cycle P5 n'est conservé.

[robot_motion.py](interfaces/robot_motion.py) conserve les mouvements temporisés :
horloge injectable, durée finie et positive ou nulle, vérification d'arrêt,
vérification d'obstacle et arrêt final même en cas d'erreur.
La période de contrôle maximale est de 20 ms ; le recul ne vérifie pas
l'obstacle frontal. Une erreur ou une absence de mesure du capteur d'obstacle
est journalisée et traitée comme un obstacle.

`stop()` transmet directement le zéro au pilote, sans attendre de verrou,
de capteur ou de temporisateur. `request_emergency_stop()` positionne d'abord
le signal d'annulation puis appelle `stop()`. Les départs de mouvement sont
inhibés tant que le signal est actif. Une lecture matérielle ou LLM bloquée
peut retarder la fin du worker, mais ne bloque pas l'appel vocal à `stop()`.
La latence physique dépend toujours du pilote et du matériel : ces contrôles
logiciels ne remplacent pas une protection indépendante qualifiée.

Les tests [de structure du runtime](../../tests/unit/test_voice_runtime_structure.py)
et [du contrôleur](../../tests/unit/test_robot_controller_structure.py) vérifient
les limites 500 lignes/module et 50 lignes/fonction et les imports matériels paresseux.
Les [tests d'arrêt d'urgence](../../tests/unit/test_emergency_stop.py) couvrent
l'arrêt sans mission, les phrases composées, la planification et l'ultrason
bloqués, ainsi que l'annulation des mouvements et des étapes suivantes.
