# Contexte projet — résumé session (2026-10-29)

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
- Objectif en cours : commande « cherche la balle jaune, approche-toi à 1 m puis suis-la 5 min » (étapes 1→10 ; étapes 3, 3b, 4, 5, 6, 7, 8 et 8b faites).
- Étape 3 perception distance : `color_detector.detect_colored_objects(..., is_rgb=False)` expose par candidat `bbox`, `area`, `diameter_px` (= sqrt(4·aire/π), invariant à la rotation) ; `choose_best_result_with_metrics` renvoie `(verdict, candidat)`, `choose_best_result` est inchangé (chaînes `BALL_YELLOW_A_GAUCHE`).
- Étape 3 : `hardware/camera/distance_estimator.py` (`estimate_distance_cm` modèle sténopé, `focal_from_known_distance`, `ExponentialSmoother` alpha 0.4, `fuse_with_ultrasound` ±25 %). `ObjectDetection` gagne `diameter_px` et `distance_visual_cm`.
- Étape 3 : `[camera]` dans `runtime_calibration.toml` (`ball_diameter_cm=6.5`, `focal_px=600.0` à calibrer, `ultrasonic_fusion=false`) -> `RuntimeSettings.camera_*`. CLI `calibrate-distance [--known-distance-cm 100]` (affiche le `focal_px` à reporter).
- Étape 3b fusion sans conflit GPIO : `SmartCar2WD.read_distance_cm()` et `check_obstacle()` partagent un `threading.Lock` + cache 50 ms (`time_fn`/`sleep_fn` injectables) ; `RobotController.read_distance_cm()` (None si absent/erreur). Le thread caméra ne calcule que l'estimation visuelle ; la fusion ultrason se fait dans `CameraLivePerceptionPipeline.detect()` (thread appelant), seulement si `ultrasonic_fusion=true`, balle au centre ; lecteur en erreur/None -> estimation visuelle. `voice_runtime.build_hardware_runtime` branche `distance_reader=robot.read_distance_cm`.
- Correctif : la pipeline caméra appelait `detect_colored_objects(is_rgb=True)` (paramètre inexistant, `TypeError` avalé -> détection toujours None) ; `picamera2` et `HC_SR04` sont des imports tolérants hors Pi.
- Étape 4 recherche/approche (`FollowTargetSkill`) : deux phases SEARCH (cible jamais vue/perdue) et TRACK (visible). En SEARCH le budget est `search_timeout_s` (défaut `settings.search_timeout_seconds`), puis `failed` + `data["target_lost"]=True` + arrêt ; `max_target_loss_s` n'est plus qu'une courte attente robot arrêté en TRACK avant de repasser en SEARCH ; `tracking_timeout_s` ne compte pas le temps de SEARCH.
- Étape 4 : balayage par impulsions dans le sens de la dernière position connue (`left`/`right`), sinon droite (pause `SEARCH_SETTLE_S`=0,15 s). `stand_off_cm` synonyme de `approach_threshold_cm` (ce dernier prioritaire), borné par `min/max_stand_off_cm` ; cible atteinte si `distance_cm <= stand_off + stand_off_tolerance_cm` (défaut 10) ; avance raccourcie (min 25 %) sous 2 x stand_off. Horloge injectable : `FollowTargetSkill(settings, time_fn, sleep_fn)`. Si `detect()` renvoie None, position/distance du blackboard sont remises à None. Chemin sans `perception.detect` inchangé. Tests : `tests/unit/test_skills_behaviors.py` (93 tests unit+integration verts ; `tests/hardware` non collectable sans gpiozero).
- Étape 5 suivi à distance constante (`FollowObjectSkill`, name `follow_object`, `behaviors/follow_object.py`, enregistré dans `behaviors/__init__`, `skills/__init__` et `SkillRegistry.default()`) : paramètres `target_object` ("yellow"), `stand_off_cm` (100, borné settings), `stand_off_tolerance_cm` (15), `duration_s` (60, borné `max_follow_duration_sec`), `max_target_loss_s` (3.0), `search_timeout_s`. Boucle 20 ms, horloge injectable (`time_fn`/`sleep_fn`). Par tour : arrêt d'urgence/obstacle -> stop + `success` + `obstacle_detected=True` (`emergency_stop=True` si urgence) ; alignement left/right d'abord (0,08 s) ; centré : trop loin -> avant (écart/`cm_per_second`, 0,05–0,25 s), trop près -> arrière (0,05–0,15 s, pas de capteur arrière), sinon zone morte (stop). Perte : stop ; au-delà de `max_target_loss_s` balayage ; retrouvée -> `reacquisitions`+1 ; sinon `failed` + `target_lost=True`. Fin : `success` avec `data={iterations, duration_s, final_distance_cm, reacquisitions}` ; `duration_s` inclut le temps de recherche ; stop garanti (`try/finally`), exception -> `failed`. Phases dans `state["follow_target_state"]` : aligning/approaching/holding/backing/searching (+ blocked/lost_target).
- Étape 5 refactor : `behaviors/target_tracking.py` (`TargetTrackingMixin`) mutualise `_detect_target`, `_check_obstacle_fail_safe`, `_pulse_motion`, `_stop_robot`, `_sweep_step` (balayage), `_is_emergency_stop_requested`, utilisé par `FollowTargetSkill` et `FollowObjectSkill`. Tests : `tests/unit/test_follow_object.py` (110 tests unit+integration verts).
- Étape 6 câblage `follow_object` : `IntentValidator.ALLOWED_INTENTS` += `follow_object` (target ∈ {None, "red", "yellow"}, sinon rejeté) ; `SkillPlanner.INTENT_TO_SKILLS["follow_object"] = ["follow_object"]`.
- Étape 6 `voice_runtime.py` : synonymes `follow`/`track`/`track_object`/`follow_target`/`suivre`/`suit` -> `follow_object` ; normalisation des cibles (`jaune`/`balle jaune`/`yellow_ball` -> `yellow`, `rouge`/`balle rouge`/`red_ball` -> `red`) pour `follow_object` et `search_and_approach_object` (`follow_red_ball` garde `red_ball`) ; `_sanitize_object_intent` appelée dans `_validate_intent_plan` : `stand_off_cm` borné [`min`,`max_stand_off_cm`] (défaut 100), `duration_s` [1, `max_follow_duration_sec`] (défaut 60), `search_timeout_s` [1, 120] (défaut `search_timeout_seconds`), non numérique/NaN -> défaut, clé absente reste absente. `_effective_step_timeout` tient compte de `search_timeout_s`. Prompt plan LLM mentionne `follow_object`.
- Étape 6 `IntentParser` (repli sans LLM) : `_extract_duration` gère minutes et nombres français 0-69 (-> secondes, `duration` des primitives inchangé) ; `_extract_stand_off_cm` (« à 1 m », « à un mètre », « à 50 cm » -> cm) ; « suis/suit/suivre » -> `follow_object` (target, `duration_s`, `stand_off_cm`) ; approche -> `search_and_approach_object` avec `stand_off_cm`. `parse_plan(text)` découpe sur « puis », « ensuite », « et puis », « , » (pas les virgules décimales), reporte cible et `stand_off_cm` aux segments « la/le/-la », fusionne cherche+approche ; utilisé en repli dans `ask_llm_for_intent_plan_with_trace` et quand `use_llm=False`. Tests : `tests/unit/test_follow_object_wiring.py` (135 tests unit+integration verts, plan complet via VoiceRuntime + FakeRobot).
- Étape 7 arrêt d'urgence : `RobotController` porte un `threading.Event` interne ; `request_emergency_stop()` (set + `stop()`), `clear_emergency_stop()`, `is_emergency_stop_requested()` ; `_is_emergency_stop_requested()` est vrai si l'événement est levé OU si le robot sous-jacent expose un détecteur (`is_emergency_stop_requested`/`check_emergency_stop`/`emergency_stop_requested`/`stop_requested`). `FollowTargetSkill` (boucle fermée) teste l'urgence à chaque tour : stop + `success` + `data["emergency_stop"]=True` + phase `blocked` (convention identique à `follow_object` : un stop demandé est une fin normale, pas une erreur ; `aborted` non utilisé).
- Étape 7 `VoiceRuntime` : paramètre `threaded=True` ; `handle_transcript(text)` lance `handle_text_as_plan` dans un thread daemon `mission-worker` ; pendant une mission, une phrase reconnue `stop` par `IntentParser` appelle `request_emergency_stop()` immédiatement, toute autre est ignorée avec un message ; `clear_emergency_stop()` est appelé dans le thread principal au démarrage d'une mission (et dans `listen_once`). `threaded=False` = chemin synchrone (tests, `--once`). Ctrl+C et `close()` -> `_abort_mission()` : urgence + `join(2 s)` du worker + `stop()`. Tests : `tests/unit/test_emergency_stop.py` (141 tests unit+integration verts, 1 skip).
- Étape 8 LLM local : modèle **Qwen2.5-1.5B-Instruct GGUF Q4_K_M** (`qwen2.5-1.5b-instruct-q4_k_m.gguf`, dépôt HF `Qwen/Qwen2.5-1.5B-Instruct-GGUF`), `llama-server --alias qwen2.5-1.5b --ctx-size 2048 --threads 4 --parallel 1`, service `llm.service` (`scripts/install/install_llm.sh`, option Ministral retirée ; `MODEL_URL`/`MODEL_FILENAME` surchargeables).
- Étape 8 `interfaces/text_normalizer.py` : `fr_numbers_to_digits` et `preprocess` portés depuis `scripts/test/eval_prompt_plan.py` (nombres en lettres -> chiffres, « N minutes » -> N*60 secondes, « N mètres » -> N*100 centimètres, « un/une » converti seulement devant une unité). Un test vérifie l'égalité avec le script (fonctions sur son corpus et `SYSTEM_PROMPT_PLAN`).
- Étape 8 correctif `preprocess` (formes composées, converties avant les simples) : « N minute(s) [et] M seconde(s) » -> (N*60+M) secondes ; « N mètre(s) [et] M [centimètre(s)] » (M 0-99) -> (N*100+M) centimètres. Sans « centimètres », M n'est pas fusionné s'il est suivi d'une autre unité (« 1 mètre et 2 secondes », « 2 mètres 3 fois »). **Écart avec `eval_prompt_plan.py`** (qui n'a pas ce correctif) : à reporter dans le script pour évaluer ces cas. Le parseur local garde sa propre gestion des minutes.
- Étape 8 `voice_runtime.py` : `preprocess` appliqué au texte envoyé au LLM (plan et intent unique) ; `raw_text` des Intent = texte d'origine, texte prétraité dans la trace (`normalized_text` de `plan_raw`). `SYSTEM_PROMPT_PLAN` = prompt de `eval_prompt_plan.py` ; `SYSTEM_PROMPT` = même liste d'intents, sortie `{intent,target,parameters,confidence}`, hors liste -> `unknown`. Payload : `temperature` 0.0, `max_tokens` 160 (plan, 120 depuis 8b) / 96 (intent), `stream` false, `cache_prompt` true, `response_format` `json_object` (remplacé en 8b par la chaîne de formats, voir ci-dessous). Réglages via env (`load_llm_settings()` dans `settings.py`, relus à chaque appel) : `LLM_MODEL` (qwen2.5-1.5b), `LLM_CONNECT_TIMEOUT_SECONDS` (1.0), `LLM_READ_TIMEOUT_SECONDS` (10.0 depuis 8c, 8.0 en 8b, 4.0 avant), `LLM_MAX_TOKENS_PLAN` (120 depuis 8b, 160 avant), `LLM_MAX_TOKENS_INTENT` (96). Préchauffage (thread daemon, prompt du plan, `max_tokens` 1) lancé par `main()` sauf `--no-llm` (`LLMWarmup` depuis 8c).
- Étape 8 robustesse : étape LLM non-dict ou `parameters` non-dict -> seule cette étape est ignorée (`skipped_steps` dans la trace) ; `confidence` absente/invalide -> 0.8 ; `unit` absente -> cm. `{"steps": []}` -> `([], source "llm_unsupported")` et `handle_text_as_plan` rejette (`status "rejected"`, `reason "unsupported command"`, événement de trace `plan_unsupported`, aucun mouvement, pas de repli parseur). Repli `IntentParser` seulement sur timeout, erreur HTTP, JSON invalide, `steps` absent/non liste ou aucune étape exploitable (parseur appelé paresseusement).
- Étape 8 `IntentParser` : extraction des nombres via `text_normalizer.fr_numbers_to_digits` (décimales « 1,5 » protégées) ; avance/recule : durée explicite, sinon distance (`distance`+`unit`), sinon 1 s ; rotations : durée, sinon angle en degrés, sinon 90°. Tests : `tests/unit/test_voice_runtime.py` (186 tests unit+integration verts, 1 skip).
- Étape 8 `scripts/install/install_llm.sh` : `PROJECT_DIR` = racine du dépôt (`scripts/install/../..`, vérifie `pyproject.toml`) -> `uv sync` fonctionne ; message final -> `uv run voice-runtime`. `REFERENCE_IROBOT.md` mis à jour (§1, 5, 6, 7, 9, 10, 11 : Qwen, `llm.service`, prompts, réglages, rejet hors périmètre, R7 corrigé).
- Étape 8b gardes déterministes (`interfaces/plan_guards.py`, portés à l'identique de `eval_prompt_plan.py`, test d'égalité) : `STOP_WORDS`, `fold`, `is_pure_stop`, `INTENT_LEXICON`, `ALLOWED_PARAMS`, `NUMERIC_KEYS`, `grounding_check`, `PLAN_SCHEMA`, `build_formats`.
- Étape 8b `handle_text_as_plan` : phrase d'arrêt pure -> plan `[stop]` exécuté sans LLM ni prétraitement (source `local_stop`, aussi en `--no-llm`) ; « avance puis arrête » passe par le LLM. Thread d'écoute pendant une mission : `is_pure_stop` d'abord, `IntentParser` en repli.
- Étape 8b plan LLM : étapes tolérantes (`target`->None, `parameters`->{}, synonymes canoniques via `PLAN_INTENT_SYNONYMS`) puis `grounding_check(texte prétraité)` avant validation : intent non justifié ou nombre faux (phrase avec chiffres) -> `([], source "llm_ungrounded")` -> `rejected`/`unsupported command`, aucun mouvement ni repli, `guard_reason`/`guard_notes` dans l'événement `plan_unsupported` ; stop parasite, paramètre non géré, nombre inventé (phrase sans chiffre) supprimés ; avance/recule sans valeur -> duration 1, tourne -> angle 90 ; notes dans `plan_raw`. `unit` reste normalisée ensuite par `_sanitize_primitive_intent`.
- Étape 8b LLM : `LLM_READ_TIMEOUT_SECONDS` 8.0 et `LLM_MAX_TOKENS_PLAN` 120 par défaut ; `ResponseFormatChain` : plan `json_schema` strict -> `json_object`+schéma -> `json_object` -> sans (passage au suivant sur HTTP 400), premier format accepté mémorisé (`reset_response_format_cache()` pour les tests) ; intent unique `json_object` -> sans. Tests : `tests/unit/test_plan_guards.py` + `test_voice_runtime.py` (232 tests unit+integration verts, 1 skip).
- Étape 8c diagnostic LLM : `_post_llm_chat(..., meta)` ; `plan_raw` contient `llm_latency_seconds` (durée réelle, même en échec), `llm_response_format` (`json_schema`|`json_object_schema`|`json_object`|`none`), `llm_attempts` (requêtes HTTP, repli de format inclus), `llm_prompt_tokens`/`llm_completion_tokens` (`usage`), `llm_timings` (copie de `timings` de llama-server), `error_type`, `warmup_status`. `LLM_RESPONSE_FORMAT` = `schema` (défaut, chaîne 8b) | `json_object` (seul) | `none` (pas de `response_format`), valeur inconnue -> `schema`. `LLM_READ_TIMEOUT_SECONDS` 10.0 par défaut (plan du use case 4,3-7,7 s serveur chaud). Démarrage à froid : `LLMWarmup` ; en `--once`/`--text` (nouvelle option de `main()`), la requête du plan attend le préchauffage (`LLM_WARMUP_WAIT_SECONDS`, défaut 60) puis part quand même ; `warmup_status` = `done`|`failed`|`timeout`|`skipped` (+ `running` en écoute continue, préchauffage non bloquant). Repli parseur annoncé en console : « [LLM] LLM trop lent (> Xs), repli sur le parseur local » (ou serveur injoignable, erreur HTTP, JSON invalide, réponse sans « steps », aucune étape exploitable). Tests : `test_voice_runtime.py` (246 tests unit+integration verts).

## 2) Choix techniques/métiers arrêtés
- Le LLM n’accède jamais au hardware directement : il produit un plan/intents validé par le runtime.
- Exécution sécurisée par whitelist d’actions, bornes distance/angle/durée, limite nombre d’étapes.
- En cas d’échec LLM plan (timeout, HTTP, JSON invalide, `steps` absent) : fallback immédiat parseur local (pas de double timeout). `{"steps": []}` = hors périmètre -> rejet, pas de fallback.
- Le LLM propose, le lexique dispose : un plan LLM non justifié par la phrase prétraitée (`grounding_check`) est rejeté sans fallback ni mouvement ; un arrêt pur (« stop », « arrête toi », « halte », « pause ») ne passe jamais par le LLM.
- Toute garde déterministe portée depuis `scripts/test/eval_prompt_plan.py` reste identique au script (test d'égalité) : modifier les deux ensemble.
- LLM : petit modèle (1,5B) -> entrée normalisée côté Python, prompt court et statique, sortie JSON minimale ; le parseur local reste le filet de sécurité.
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
- Étapes 9→10 de la commande vocale « cherche/approche à 1 m/suis 5 min » (à fournir une par une).
- Mesurer sur le Pi 5 la latence/débit de Qwen2.5-1.5B (`eval_prompt_plan.py --repeat 3`) et l'effet de `cache_prompt` + préchauffage dans le budget de 10 s (`LLM_READ_TIMEOUT_SECONDS`), comparer `LLM_RESPONSE_FORMAT` schema/json_object/none via `llm_timings` de la trace, et le taux de faux rejets du contrôle lexical (`eval_prompt_plan.py` sans `--no-guards`).
- Restes Ministral / `ctx-size 4096` hors chemin Pi : `install_llm_mac_portable.sh`, `run_llm_runtime_mac.sh`, `docs/guide-installation-llm-mac-portable.md`, `commandes.txt`, `tests/integration/test_voice_runtime_llm_integration.py` ; `hardware/audio/voice_assistant.py` (legacy) lit `LLM_MODEL` sans prétraitement ni timeouts ; README cite encore `uv run voice-assistant` (commandes audio).
- Voie legacy `handle_text` : `unknown` du LLM -> repli parseur (pas de rejet comme en voie plan).
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
- configure le service `llm.service` (Qwen2.5-1.5B-Instruct GGUF Q4_K_M, `--alias qwen2.5-1.5b`, `--ctx-size 2048`)
- `uv sync` sur la racine du dépôt ; sans argument (`MODEL_URL`/`MODEL_FILENAME` surchargeables par l'environnement)

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
- modèle : Qwen2.5-1.5B-Instruct (GGUF Q4_K_M), `--ctx-size 2048`, service `llm.service`
- API compatible OpenAI : `/v1/chat/completions` (appel non streamé, timeout lecture 8 s, `response_format` `json_schema` avec replis, `cache_prompt`)
- le modèle est utilisé pour générer des réponses à partir de la transcription
- il peut aussi servir à produire une intention structurée à partir d'une phrase libre, mais le moteur de contrôle reste le planificateur de skills

En pratique :
- le flux audio -> Vosk -> texte
- texte -> prétraitement déterministe (`text_normalizer.preprocess`) -> LLM ou parser -> `Intent`
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
- le chargement du modèle est lent au premier démarrage (préchauffage en arrière-plan au lancement de `voice-runtime` ; les premières commandes peuvent tomber en repli parseur)
- certaines versions de `llama-server` refusent `json_schema` ou `response_format` (HTTP 400) : le runtime essaie `json_schema` strict -> `json_object`+schéma -> `json_object` -> sans, et mémorise le premier format accepté (jusqu'au redémarrage du runtime)
- un petit LLM range parfois une phrase hors périmètre dans l'intent le plus proche (« chante une chanson » -> `spin_360`) : c'est le rôle de `plan_guards.grounding_check` ; un mot de commande absent de `INTENT_LEXICON` provoque un faux rejet (à enrichir dans le script ET dans `plan_guards.py`)
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