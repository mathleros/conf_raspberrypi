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
