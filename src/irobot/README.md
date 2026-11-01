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

## Organisation du runtime vocal

Le point d'entrée public reste `interfaces/voice_runtime.py` (`voice-runtime`,
`VoiceRuntime`, fonctions LLM de compatibilité et `build_hardware_runtime`).
Les responsabilités sont réparties ainsi :

| Module | Responsabilité |
| --- | --- |
| `interfaces/voice_state.py` | État partagé, configuration, contrôleur et écriture JSONL |
| `interfaces/voice_constants.py` | Vocabulaire et valeurs par défaut des plans |
| `interfaces/voice_llm_transport.py` | Prompts, HTTP, formats de réponse, métriques et cache |
| `interfaces/voice_llm.py` | Reconstruction des intentions, grounding, repli local et préchauffage |
| `interfaces/voice_plan.py` | Normalisation, bornage, expansion et validation déterministes |
| `interfaces/voice_execution.py` | Séquence de mission, retries, délais et traces d'exécution |
| `interfaces/voice_protection.py` | Admission, réservations, supervision et raccordement humain structuré |
| `hardware/audio/voice_input.py` | Capture ALSA, nettoyage du processus et transcription Vosk |
| `hardware/voice_runtime_factory.py` | Assemblage réel moteur/capteur/caméra sur Raspberry Pi |

Les trois mixins de planification, exécution et protection utilisent un unique
état partagé, sans recopier les verrous ni les permis. Les adaptateurs matériels
sont importés uniquement lors de leur utilisation ; charger le runtime ou traiter
du texte n'initialise ni ALSA, ni Vosk, ni GPIO, ni caméra. L'assemblage live conserve
son refus lorsqu'une protection est déclarée sans adaptateur P5 qualifié.
Le LLM reste un producteur d'intentions, jamais un pilote matériel.

Tous les modules de ce découpage respectent 500 lignes maximum et toutes leurs
fonctions 50 lignes maximum (décorateurs compris). Le test
`tests/unit/test_voice_runtime_structure.py` contrôle ces limites, les imports
matériels paresseux et les contrats des adaptateurs sur doubles.

## Organisation du contrôleur robot

Le point d'entrée public reste `interfaces/robot_controller.py` :
`RobotController` et l'import historique de `MissionRobot` sont conservés.

| Module | Responsabilité |
| --- | --- |
| `interfaces/robot_controller.py` | Façade, état partagé, verrous, interruptions prioritaires, validation P5 et accès au pilote injecté |
| `interfaces/robot_admission.py` | Admission, réservation, acquisition, activation, maintien et suspension/reprise |
| `interfaces/robot_supervision.py` | Cycle protégé, préconditions, journal, revalidation avant émission et preuve de cycle |
| `interfaces/robot_motion.py` | Mouvements temporisés, échéance fixe, attente interruptible et arrêt final |
| `interfaces/mission_robot.py` | Capacité restreinte liée à un permis, sans accès au pilote ni délégation |

Les modules auxiliaires travaillent sur le même contrôleur, sans recopier
l'état de mission ni les verrous. Le contexte de supervision ne conserve que
les faits d'un cycle ; les appels aux méthodes du contrôleur restent dynamiques.
L'ordre des contrôles, des lectures P5, des écritures de journal et des émissions
est conservé, tout comme les résultats historiques du chemin non protégé.
Le matériel concret reste dans `hardware` : aucun de ces modules ne l'importe
ou ne l'initialise, et les ports de protection restent explicitement injectés.

Le test `tests/unit/test_robot_controller_structure.py` vérifie les limites
500 lignes/module et 50 lignes/fonction (décorateurs compris), l'absence
d'imports matériels, la compatibilité de la capacité et le mouvement temporisé.
Il est inclus dans les campagnes isolées pytest et stdlib du lot A.

## Organisation de la perception et du suivi humain

Les imports publics de `interfaces/human_perception.py` et
`interfaces/human_follow_runtime.py` restent disponibles.

| Module | Responsabilité |
| --- | --- |
| `interfaces/human_perception_contracts.py` | Types immuables, contexte de mission, protocoles source/fournisseur et validation numérique commune |
| `interfaces/human_perception.py` | Validation de provenance, fraîcheur, séquences, géométrie et confirmations d'acquisition |
| `interfaces/aruco_marker_decoder.py` | Décodage de l'identifiant configuré et normalisation des résultats via une API injectée |
| `hardware/camera/aruco_backend.py` | Chargement concret et paresseux de l'API OpenCV ArUco |
| `interfaces/human_follow_runtime.py` | Façade, validation avant admission, état unique, journal, échéances et suspension/reprise |
| `interfaces/human_follow_perception.py` | Lecture source/fournisseur, revalidation des résultats en vol, générations retirées et décisions d'acquisition |
| `interfaces/human_follow_announcements.py` | Annonces structurées, invalidation, textes et activation après confirmation explicite |

Les auxiliaires utilisent la même session, sans recopier permis, contexte ni
état d'acquisition. Les arrêts, échéances et changements de contexte restent
prioritaires sur les résultats produits pendant une lecture ou un décodage.
L'API ArUco injectée fonctionne sans imports matériels ; le backend concret
n'est chargé qu'à la construction d'un décodeur sans API injectée.
Aucun adaptateur caméra, parole ou mouvement humain réel n'est ajouté.

`tests/unit/test_human_runtime_structure.py` contrôle les limites 500/50,
les imports matériels paresseux et la compatibilité des imports publics ;
il appartient aux sélections humaines et complètes isolées du lot A.

## Garde-fous humains SH-05

Le chemin déclaré protégé revalide admission, contexte, P5, préconditions,
arrêts et échéance avant émission. Stop/annulation rendent aussi les demandes
d'admission antérieures obsolètes ; effacer le stop logiciel ne les restaure
pas et ne réarme jamais P5.

`RobotController(..., human_motion_limits=...)` accepte uniquement une
enveloppe immuable `HumanMotionLimits` explicitement injectée. Son identifiant
renvoie à une qualification externe : le plafond de réglage du driver n'est
pas une conversion en vitesse au sol. La borne déclarée au sol ne peut
dépasser 0,15 m/s. Sans enveloppe, toute émission humaine non nulle est
refusée, même avec des préconditions positives ; la préparation immobile
reste possible. Aucun profil de production n'est fourni.

Les rotations exigent les trois bornes explicitement fournies (vitesse
angulaire majorée, angle, durée), une commande temporisée et toutes les
préconditions, notamment cible actuelle et volume balayé protégé. Rotation
directe non bornée, recul et commande inconnue sont refusés. Le cycle
temporisé recontrôle ses conditions sans réémettre le mouvement et ne
repousse pas son échéance logicielle après une attente de journal/port.
Un port ou une boucle bloqués peuvent empêcher la remise du zéro : seule
la protection indépendante qualifiée couvre ce cas physique.

Sur le chemin protégé, un stop terminé remonte `stopped`, sans succès de
mission, réessai ni étape suivante. Une suspension et une fin humaine
remontent aussi mission/contexte/armement, échéance initiale, causes et
action requise. Le statut historique balle `in_progress` reste interprétable
par sa politique de réessai ; il n'autorise pas une étape suivante.
Le chemin non protégé conserve ses résultats de stop historiques.

Voir les [preuves logicielles SH-05](../../specs/backlog/08_lot_a_rapport_sh09.md#18-sh-05--complément-logiciel-et-campagne-isolée-2026-10-31)
et les [blocages physiques distincts](../../docs/test-campaign/sh05-blocages-physiques.md).
Le raccordement humain reste injecté, sans fournisseur de mouvement réel ;
aucune commande naturelle humaine ni motorisation n'est activée.
