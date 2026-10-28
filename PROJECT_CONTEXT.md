# Contexte projet — résumé session (2026-10-28)

## Feuille de route & Chantiers en cours
- Référence d'audit : `docs/audit-architecture-2026.md`
- [ ] **Chantier P1 :** Restauration des points d'entrée et nettoyage legacy (En cours)
- [ ] **Chantier P2 :** Sécurité matérielle & Mouvements non bloquants
- [ ] **Chantier P3 :** Boucle de contrôle fermée
- [ ] **Chantier P4 :** Factorisation DRY & Typage
- [ ] **Chantier P5 :** Gestion asynchrone LLM & Watchdog

## 1) Réalisé et validé
- Runtime LLM local Mac consolidé : `run_llm_runtime_mac.sh` + saisie texte + mode mock objet.
- Mode hybride planification : support `execute_path`, normalisation, bornage strict des paramètres, fallback local rapide.
- Pipeline mission renforcé : validation de plan, retries par étape, timeout mission/step, statuts finaux (`success`/`incomplete`/`aborted`).
- Traçabilité complète : traces JSONL, `TRACE_PATH`, script replay `replay_runtime_trace_mac.sh`.
- Préparation Mac avant Pi : scripts `run_mission_mac.sh`, `run_runtime_standard_scenarios_mac.sh`, protocoles/checklists/backlog.
- Nettoyage doublons/doc : `detect_red_ball.py` converti en shim compat, docs centralisées.
- Validation : suite unitaire verte (82 tests dans `tests/unit`).
- Étape 1 sécurité : durée par défaut injectée (1.0 s avance/recul, 90° rotation) quand aucun distance/angle/duration, bornée par `max_duration_sec`.
- Étape 1 sécurité : normalisation des unités de distance (`m`/mètres… -> `m`, `cm`/centimètres… et inconnues -> `cm`) via `normalize_distance_unit`, au runtime et dans les primitives.
- Étape 1 sécurité : `robot.stop()` garanti en fin de mission (`try/finally`, exceptions ignorées).
- Étape 1 sécurité : arrêt de l'exécution après une étape `rejected`/`failed`/`incomplete`/`aborted`.
- Étape 1 sécurité : plan rejeté en entier si une étape est invalide (`reason: "invalid plan step"`, `validation_errors` conservé).
- Objectif en cours : commande « cherche la balle jaune, approche-toi à 1 m puis suis-la 5 min » (étapes 1→10 ; étapes 3, 3b, 4 et 5 faites).
- Étape 3 perception distance : `color_detector.detect_colored_objects(..., is_rgb=False)` expose par candidat `bbox`, `area`, `diameter_px` (= sqrt(4·aire/π), invariant à la rotation) ; `choose_best_result_with_metrics` renvoie `(verdict, candidat)`, `choose_best_result` est inchangé (chaînes `BALL_YELLOW_A_GAUCHE`).
- Étape 3 : `hardware/camera/distance_estimator.py` (`estimate_distance_cm` modèle sténopé, `focal_from_known_distance`, `ExponentialSmoother` alpha 0.4, `fuse_with_ultrasound` ±25 %). `ObjectDetection` gagne `diameter_px` et `distance_visual_cm`.
- Étape 3 : `[camera]` dans `runtime_calibration.toml` (`ball_diameter_cm=6.5`, `focal_px=600.0` à calibrer, `ultrasonic_fusion=false`) -> `RuntimeSettings.camera_*`. CLI `calibrate-distance [--known-distance-cm 100]` (affiche le `focal_px` à reporter).
- Étape 3b fusion sans conflit GPIO : `SmartCar2WD.read_distance_cm()` et `check_obstacle()` partagent un `threading.Lock` + cache 50 ms (`time_fn`/`sleep_fn` injectables) ; `RobotController.read_distance_cm()` (None si absent/erreur). Le thread caméra ne calcule que l'estimation visuelle ; la fusion ultrason se fait dans `CameraLivePerceptionPipeline.detect()` (thread appelant), seulement si `ultrasonic_fusion=true`, balle au centre ; lecteur en erreur/None -> estimation visuelle. `voice_runtime.build_hardware_runtime` branche `distance_reader=robot.read_distance_cm`.
- Correctif : la pipeline caméra appelait `detect_colored_objects(is_rgb=True)` (paramètre inexistant, `TypeError` avalé -> détection toujours None) ; `picamera2` et `HC_SR04` sont des imports tolérants hors Pi.
- Étape 4 recherche/approche (`FollowTargetSkill`) : deux phases SEARCH (cible jamais vue/perdue) et TRACK (visible). En SEARCH le budget est `search_timeout_s` (défaut `settings.search_timeout_seconds`), puis `failed` + `data["target_lost"]=True` + arrêt ; `max_target_loss_s` n'est plus qu'une courte attente robot arrêté en TRACK avant de repasser en SEARCH ; `tracking_timeout_s` ne compte pas le temps de SEARCH.
- Étape 4 : balayage par impulsions dans le sens de la dernière position connue (`left`/`right`), sinon droite (pause `SEARCH_SETTLE_S`=0,15 s). `stand_off_cm` synonyme de `approach_threshold_cm` (ce dernier prioritaire), borné par `min/max_stand_off_cm` ; cible atteinte si `distance_cm <= stand_off + stand_off_tolerance_cm` (défaut 10) ; avance raccourcie (min 25 %) sous 2 x stand_off. Horloge injectable : `FollowTargetSkill(settings, time_fn, sleep_fn)`. Si `detect()` renvoie None, position/distance du blackboard sont remises à None. Chemin sans `perception.detect` inchangé. Tests : `tests/unit/test_skills_behaviors.py` (93 tests unit+integration verts ; `tests/hardware` non collectable sans gpiozero).
- Étape 5 suivi à distance constante (`FollowObjectSkill`, name `follow_object`, `behaviors/follow_object.py`, enregistré dans `behaviors/__init__`, `skills/__init__` et `SkillRegistry.default()`) : paramètres `target_object` ("yellow"), `stand_off_cm` (100, borné settings), `stand_off_tolerance_cm` (15), `duration_s` (60, borné `max_follow_duration_sec`), `max_target_loss_s` (3.0), `search_timeout_s`. Boucle 20 ms, horloge injectable (`time_fn`/`sleep_fn`). Par tour : arrêt d'urgence/obstacle -> stop + `success` + `obstacle_detected=True` (`emergency_stop=True` si urgence) ; alignement left/right d'abord (0,08 s) ; centré : trop loin -> avant (écart/`cm_per_second`, 0,05–0,25 s), trop près -> arrière (0,05–0,15 s, pas de capteur arrière), sinon zone morte (stop). Perte : stop ; au-delà de `max_target_loss_s` balayage ; retrouvée -> `reacquisitions`+1 ; sinon `failed` + `target_lost=True`. Fin : `success` avec `data={iterations, duration_s, final_distance_cm, reacquisitions}` ; `duration_s` inclut le temps de recherche ; stop garanti (`try/finally`), exception -> `failed`. Phases dans `state["follow_target_state"]` : aligning/approaching/holding/backing/searching (+ blocked/lost_target).
- Étape 5 refactor : `behaviors/target_tracking.py` (`TargetTrackingMixin`) mutualise `_detect_target`, `_check_obstacle_fail_safe`, `_pulse_motion`, `_stop_robot`, `_sweep_step` (balayage), `_is_emergency_stop_requested`, utilisé par `FollowTargetSkill` et `FollowObjectSkill`. Tests : `tests/unit/test_follow_object.py` (110 tests unit+integration verts).

## 2) Choix techniques/métiers arrêtés
- Le LLM n’accède jamais au hardware directement : il produit un plan/intents validé par le runtime.
- Exécution sécurisée par whitelist d’actions, bornes distance/angle/durée, limite nombre d’étapes.
- En cas d’échec LLM plan : fallback immédiat parseur local (pas de double timeout).
- Priorité sécurité : obstacle > mouvement (arrêt prioritaire).
- Calibration paramétrable par fichier : `config/runtime_calibration.toml`.
- Distance balle : estimation visuelle (diamètre apparent, frame 640x480 tournée de 90°) lissée ; ultrason optionnel, jamais lu depuis le thread caméra (HC-SR04 chronométré à la main : lectures concurrentes non sûres).
- Organisation dépôt maintenue : `scripts/install`, `scripts/test`, `tests`, `specs/backlog`.

## 3) Restant / prochaines étapes
- Finaliser passage Pi réel : câblage moteur réel + calibration terrain (distance/angle).
- Brancher perception caméra live (remplacer simulation/mock) et valider approche objet en boucle fermée.
- Exécuter protocole scénarios standard sur Pi (3 runs/scénario) + mesures/tolérances.
- Produire rapport d’intégration Pi (template backlog) et décider GO/NO-GO.
- Mettre à jour/réduire les références doc héritées si besoin après premiers tests Pi.
- Calibrer `focal_px` sur le Pi (`calibrate-distance --known-distance-cm 100`) puis activer `ultrasonic_fusion` si les mesures sont cohérentes.
- Étapes 6→10 de la commande vocale « cherche/approche à 1 m/suis 5 min » (à fournir une par une).
- prépare le système pour l’utilisation des GPIO

### `scripts/install_respeaker.sh`
- configure les overlays `wm8960-soundcard` et SPI
- installe `alsa-utils`, `i2c-tools`, etc.
- crée un service `systemd` pour restaurer les paramètres audio au boot

### `scripts/install_llm.sh`
- installe les dépendances système de compilation
- clone `llama.cpp`
- compile `llama-server`
- télécharge le modèle local
- configure le service `llm.service (modèle par défaut qwen2.5-1.5b, choix via --model ou LLM_MODEL)`

### `scripts/install_bluetooth_audio.sh`
- installe `bluez`, `pulseaudio`, `alsa-utils`
- active le service Bluetooth
- configure un helper de diagnostic pour les sources audio Bluetooth

### `scripts/connect_jabra_bt.sh`
- scan Bluetooth
- appairage / connexion à un casque Jabra
- vérifie les sources audio disponibles

## 11. Installation recommandée

Le README et les scripts suggèrent généralement ce flux :

1. installer Raspberry Pi OS 64 bits
2. activer SSH
3. mettre à jour le système
4. installer le support GPIO
5. installer le ReSpeaker si besoin
6. installer le support Bluetooth audio si besoin
7. installer `llama.cpp` + modèle local + Vosk
8. lancer le système de test ou la commande vocale

## 12. Modèle LLM local

Le projet vise un fonctionnement local, sans dépendance à un cloud.

- `llama-server` écoute sur `127.0.0.1:8080`
- API compatible OpenAI : `/v1/chat/completions`
- le modèle est utilisé pour générer des réponses à partir de la transcription
- il peut aussi servir à produire une intention structurée à partir d'une phrase libre, mais le moteur de contrôle reste le planificateur de skills

En pratique :
- le flux audio -> Vosk -> texte
- texte -> LLM ou parser -> `Intent`
- `Intent` -> planifier -> exécution via skills

## 13. Points de vigilance / pièges connus

### Caméra
- la caméra OV5647 n’a pas toujours un auto-detect fiable
- `config.txt` peut nécessiter `dtoverlay=ov5647,cam1`

### Audio
- le HAT ReSpeaker est optionnel
- le projet supporte également un casque Bluetooth Jabra / source audio Bluetooth
- le mode audio est résolu automatiquement via `resolve_input_device()`

### GPIO
- HC-SR04 : une seule lecture à la fois (verrou dans `SmartCar2WD`, cache 50 ms) ; ne jamais le lire depuis le thread caméra
- toutes les broches sont BCM, pas physiques
- GND du Pi doit être relié au GND du module L298N
- ne pas alimenter les moteurs directement via le Raspberry Pi

### LLM
- le chargement du modèle est lent au premier démarrage
- les services doivent être lancés avec le bon utilisateur systemd
- le chemin du binaire/model est critique

## 14. Hypothèses de conception

Le dépôt montre clairement une logique de preuve de concept / validation physique :
- chaque module est testable séparément
- le but n’est pas d’avoir un backend robuste ou un produit prêt pour la production
- le code est orienté démonstration, expérimentation et prototypage embarqué
- le flux de commande est désormais cadré par une architecture en `Intent` + `skills`

## 15. Points importants pour les échanges futurs

Quand on travaille sur ce projet, il faut garder à l’esprit que :
- la plupart des composants exigent un environnement Raspberry Pi réel
- la majorité des scripts sont basés sur des interfaces système (GPIO, ALSA, SPI, Bluetooth, système file)
- le code est très dépendant du matériel
- des erreurs peuvent venir de l’OS, de la configuration du device tree, des overlays, ou des dépendances apt
- le projet repose sur `uv` et sur les outils système installés par les scripts
- les évolutions de l'architecture doivent rester cohérentes entre `domain`, `interfaces` et `hardware`

## 16. Règle de maintenance du contexte

Le fichier `PROJECT_CONTEXT.md` est un document vivant et doit être mis à jour systématiquement dès que l’on apprend une information utile, un changement de configuration, une évolution de l’architecture, un nouveau composant, un correctif ou une convention de travail.

Règle de travail :
- si une donnée est nouvelle ou modifie le contexte du projet, elle doit être ajoutée ici
- si un comportement réel diffère du contexte documenté, ce dernier doit être corrigé
- si une commande, un script ou une convention importante est découverte, elle doit être intégrée
- le contexte ne doit pas rester figé tant que le projet évolue

Objectif : garantir que la mémoire du projet reste exacte, exploitable et cohérente d’une conversation à l’autre.

## 17. Conclusion

Ce dépôt est un environnement de démonstration / laboratoire sur Raspberry Pi dédié à :
- la commande matérielle locale
- la vision par caméra
- la commande vocale hors ligne
- la voiture autonome de prototype
- la transformation d’une phrase naturelle en plan de skills validé

Le code est compréhensible et modulaire, mais il dépend fortement du contexte matériel et système. Pour toute modification future, il faut toujours se référer à la fois au code Python et au contexte logiciel système (GPIO, ALSA, SPI, Bluetooth, `llama-server`, `systemd`, device tree).

Ce document sert comme base de contexte pour travailler plus vite et plus correctement sur les prochaines itérations.