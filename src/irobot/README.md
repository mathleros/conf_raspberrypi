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

## Configuration

La calibration du runtime est chargée depuis
[config/runtime_settings.toml](config/runtime_settings.toml). Les sections,
clés et types TOML sont vérifiés au chargement ; une clé inconnue ou une valeur
mal typée déclenche une erreur explicite. Les paramètres du client LLM sont
séparés dans `config/llm_settings.py` et proviennent des variables `LLM_*`.
Les imports historiques depuis `config/settings.py` restent compatibles.

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
| `hardware/runtime_factory.py` | Assemblage moteur/capteur/caméra sur Raspberry Pi |

Les deux mixins de planification et d'exécution utilisent un unique état partagé.
Les anciens modules de protection, d'admission et de suivi humain ne sont plus
requis. Les adaptateurs matériels sont importés uniquement lors de leur utilisation :
charger le runtime ou traiter du texte n'initialise ni ALSA, ni Vosk, ni GPIO, ni caméra.

La perception caméra attend une image traitée pour la cible demandée au démarrage
et lors d'un changement de cible (par exemple balle rouge vers marqueur avec
« suis-moi »). Une image encore en traitement pour l'ancienne cible ne satisfait
pas cette attente, limitée à une seconde et interrompue à la fermeture ou en cas
d'échec caméra. Un dépassement est journalisé et ne fournit aucune détection.
Les intentions `follow_person`, `follow_red_ball` et `follow_object` utilisent
le même suivi continu, sans limite de tentatives, de tracking ou de recherche
lorsqu'aucune durée n'est demandée. À distance de consigne, le robot attend puis
reprend si la cible s'éloigne. Lors d'une perte de cible, il arrête la translation,
attend le délai de perte courte puis recherche en rotation jusqu'à réacquisition
ou arrêt. Cela vaut aussi pour le marqueur ArUco.
Une durée explicitement demandée (`duration_s`) conserve le mode temporisé et
ses bornes. `search_and_approach_object` reste une approche ponctuelle bornée,
y compris « approche-toi de moi » avec ou sans LLM.
Les arrêts vocaux, les obstacles, la validation et les erreurs matérielles restent
prioritaires ; une erreur de suivi n'est pas relancée automatiquement.
Les traces `step_result` incluent le statut, le message et les données des skills.
Le runtime n'intègre pas d'adaptateur P5 qualifié ; toute protection matérielle
doit fonctionner indépendamment du logiciel.

La distance ArUco du runtime et du diagnostic utilise la même fonction
[estimate_marker_distance_cm](hardware/camera/detector/aruco_detector.py) : pose
`solvePnP` à partir des quatre coins, puis distance directe objectif–centre
du marqueur. L'inclinaison et le décentrage sont pris en compte. Le carré est
supposé mesurer 8 cm ; la focale provisoire est 600 px pour l'image tournée
480×640, avec centre optique centré et distorsion nulle. Sans calibration
optique, la précision réelle, notamment aux bords, reste à vérifier sur le Pi.
Une pose inexploitable est journalisée et ne fournit aucune détection, sans
repli sur la largeur apparente. L'estimation des balles, les seuils de position
et l'absence de fusion ultrason pour les marqueurs restent inchangés.

## Correction du contre-jour

[frame_enhancer.py](hardware/camera/frame_enhancer.py) partage la correction entre
le runtime, `vision-detect-live` (y compris son mode aperçu) et
`calibrate-distance`. Les images restent en RGB jusqu'à la conversion propre
au détecteur ou à l'affichage. Le CLAHE est créé une seule fois par flux et
appliqué uniquement au canal de luminosité L de LAB, avant toute détection.

Dans [runtime_settings.toml](config/runtime_settings.toml), section
`[camera]`, la correction est activée avec `exposure_value = 1.0` EV,
`clahe_enabled = true`, `clahe_clip_limit = 3.0` et une grille fixe 8×8.
La compensation d'exposition est transmise à Picamera2 après configuration et
avant démarrage ; elle dépend de l'exposition automatique de la caméra.
Si `ExposureValue` n'est pas disponible, un avertissement est journalisé et le
CLAHE reste utilisable. Une erreur de réglage n'est pas masquée.

Pour retrouver le comportement précédent, régler `exposure_value = 0.0` et
`clahe_enabled = false`. Ces valeurs sont aussi les défauts lorsque les clés
sont absentes. Un booléen CLAHE invalide, une limite non positive ou une
exposition non finie/hors de [-8, 8] EV est refusé explicitement.

Le traitement améliore le contraste local mais ne récupère pas les détails
déjà perdus par sous-exposition ou saturation. Une compensation positive peut
surexposer l'arrière-plan ; le CLAHE peut amplifier le bruit et modifier les
valeurs HSV malgré la conservation des canaux a/b. Vérifier sur le Pi les
balles rouge/jaune, les IDs ArUco, les faux positifs et la latence, en éclairage
normal et en contre-jour. Refaire la calibration de distance avec les mêmes
réglages que le runtime si la segmentation et les diamètres mesurés changent.

## Détection de visages

[face_detector.py](hardware/camera/detector/face_detector.py) utilise YuNet uniquement
pour les cibles explicites `face` et `human` (alias). Le runtime applique d'abord
le même CLAHE que pour les balles/ArUco, puis le wrapper convertit RGB vers BGR.
Le modèle est chargé à la première image demandée pour un visage, jamais pour
une balle ou un marqueur. Un modèle absent ou invalide et une erreur YuNet sont
signalés explicitement ; une erreur de capture arrête le flux sans détection.

Le modèle [face_detection_yunet_2023mar.onnx](../../assets/vision/face_detection_yunet_2023mar.onnx)
provient d'[OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet),
sous [licence MIT](../../assets/vision/face_detection_yunet_LICENSE.txt).
Taille : 232 589 octets ; SHA-256 :
`8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`.
Il est livré avec le projet, sans téléchargement automatique au démarrage.

La section `[camera]` de [runtime_settings.toml](config/runtime_settings.toml)
configure `face_model_path` (relatif au TOML ou absolu), `face_width_cm = 15.0`,
`face_score_threshold = 0.45` et `face_grace_frames = 10`.
La distance indicative vaut `focal_px × face_width_cm / largeur_du_visage_px`,
avec la focale caméra existante et les pixels de l'image orientée, sans fusion
ultrason. Largeur et seuil doivent être finis et positifs, le seuil au plus 1,
et la tolérance un entier non négatif.

Le visage de plus grande largeur admissible est sélectionné ; sa sortie est
un `ObjectDetection(label="face")` avec position, distance, confiance et largeur
dans `diameter_px`. La mémoire conserve la dernière observation jusqu'à N images
traitées sans visage, puis retourne `None`. Elle est effacée lors d'un changement
de cible, de dimensions ou d'une erreur YuNet ; une réacquisition remet le compteur
à zéro. Les appels répétés à `detect()` ne consomment pas cette tolérance.
Pendant la grâce, position/distance/confiance sont celles de l'ancienne observation,
pas des mesures actuelles ; la durée réelle dépend du débit caméra. Régler
`face_grace_frames = 0` pour que toute perte soit immédiatement visible au suivi.

Il s'agit de détection, pas de reconnaissance d'identité : plusieurs visages
peuvent provoquer un changement de personne suivie. La distance varie avec la
largeur réelle et l'orientation du visage et doit être vérifiée sur le Pi avant
suivi moteur. Aucune image ni donnée biométrique n'est enregistrée par le wrapper.
Les contrôleurs de suivi existants acceptent la source `face` sans nouveau contrat.
La commande vocale « suis-moi » et les cibles `marker`/`me` restent liées au
marqueur ArUco : cette modification ne change pas le parseur ni les prompts LLM.

## Diagnostic vision

`uv run vision-detect-live` lance [vision_diagnostic.py](tools/vision_diagnostic.py)
sur la caméra 0 OV5647, avec affichage X11 et rotation habituelle de 90°.
Il recherche simultanément l'ID ArUco `DICT_4X4_50 / 1`, le visage sélectionné
par YuNet et la meilleure balle de chacune des couleurs rouge et jaune.
Le CLAHE n'est appliqué qu'une fois à chaque image avant les trois détecteurs.
Le visage et les balles ont des rectangles distincts ; le marqueur conserve
ses quatre coins et sa distance par pose. Les statuts et distances sont affichés
à l'écran et journalisés lors de changements. Les objets colorés non classés
comme balles ne sont pas présentés comme balles.

`uv run vision-detect-live --preview-only` affiche le même flux corrigé et tourné,
sans lancer les détecteurs, afficher de statut ni annoter l'image.

Un visage conservé pendant le délai de grâce est marqué `memorized`, avec sa
dernière boîte et ses anciennes mesures. Le diagnostic utilise les réglages
caméra du TOML, ne commande aucun moteur et n'enregistre aucune image.
Le modèle YuNet doit être disponible ; une erreur de détection n'est pas
assimilée à une absence. Appuyer sur `q` ou Ctrl+C pour quitter.
Pour le lancement Python direct, utiliser `python -m irobot.tools.vision_diagnostic`.

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
mouvements, vitesse, surveillance du capteur injecté et arrêt d'urgence logiciel.
Le pilote [SmartCar2WD](hardware/smart_car/smart_car.py) ne gère que les moteurs
et leurs GPIO ; le CLI est séparé dans [hardware/smart_car/cli.py](hardware/smart_car/cli.py).
Aucun mode protégé, permis de mission ou cycle P5 n'est conservé.

`RobotController` gère aussi les mouvements temporisés : horloge injectable,
durée finie et positive ou nulle, vérification d'arrêt, vérification d'obstacle
et arrêt final même en cas d'erreur.
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
