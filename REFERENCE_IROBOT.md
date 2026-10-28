# Référence projet — `mathleros-conf_raspberrypi` (package `irobot`)

> Document de référence pour l'écriture et la mise au point des **prompts LLM** du projet.
> Basé sur une lecture du dump du dépôt (`mathleros-conf_raspberrypi-*.txt`, ~11 500 lignes).
> Date d'analyse : 2026-10-27. Les affirmations marquées **(à vérifier)** ne sont pas démontrées par le code seul.

---

## 0. Couverture de l'analyse

**Lu en détail** : `README.md`, `PROJECT_CONTEXT.md`, `pyproject.toml`, `config/runtime_calibration.toml`, `settings.py`, tout `domain/` (orchestrator + skills), tout `interfaces/` (`intent_parser`, `language_controller`, `robot_controller`, `voice_runtime`, `perception_pipeline`), `camera_live_pipeline.py`, squelette de `smart_car.py`, `specs/03_llm_model_strategy.md`, `docs/audit-v5`, `install_llm.sh` (paramètres), liste des tests.

**Survolé seulement** : `color_detector.py` (~380 lignes), `hc_sr04.py`, `audio_utils.py`, `voice_assistant.py` (legacy), `simulated_perception.py`, scripts d'install/test, `specs/01`, `specs/02`, backlog, audits v1–v4, tests hardware.

**À relire si un sujet y touche** : détection couleur (seuils HSV), pilotage audio, `specs/02_functional_technical_architecture.md`.

---

## 1. Vue d'ensemble

Banc d'essai robotique sur **Raspberry Pi 5** : voiture **Smart Car 2WD** (pont en H L298N), caméra CSI OV5647, capteur ultrason HC-SR04, micro (ReSpeaker 2-Mic HAT ou casque Bluetooth Jabra), assistant vocal **100 % local**.

Principe d'architecture (décision arrêtée) : **le LLM ne touche jamais le matériel**. Il produit uniquement des *intents* en JSON ; un runtime Python valide, borne, planifie et exécute via des *skills*.

```
Micro → arecord (16 kHz mono) → Vosk (STT fr) → texte
   → [LLM local : plan JSON]  ──(échec/timeout)──► IntentParser (regex, local)
   → normalisation des noms → expansion (execute_path, spin, square, contour, return_to_start)
   → validation + bornage → exécution étape par étape (retry, timeouts, trace JSONL)
   → LanguageController.handle_intent → SkillPlanner → SkillExecutor → Skills → RobotController → SmartCar2WD (GPIO)
```

Stack : Python ≥ 3.12 (`.python-version` = 3.13), `uv`, `opencv-python`, `requests`, `gpiozero` (Linux), `vosk` (Linux), `pytest`. LLM : `llama.cpp` (`llama-server`) + **Ministral-3-3B-Instruct-2512 Q4_K_M**, API OpenAI-compatible sur `127.0.0.1:8080`, service systemd `ministral.service`.

---

## 2. Carte du code

```
src/irobot/
├── config/settings.py              RuntimeSettings + lecture de config/runtime_calibration.toml
├── domain/
│   ├── orchestrator/
│   │   ├── planner.py              INTENT_TO_SKILLS (mapping déterministe intent → skills)
│   │   ├── registry.py             SkillRegistry.default() (9 skills)
│   │   ├── executor.py             valide puis exécute 1 skill
│   │   ├── mission_state_machine.py idle/planning/executing/success/failed/aborted
│   │   └── calibration_helpers.py  conversions distance/angle → durée (apparemment non utilisé par les skills)
│   └── skills/
│       ├── base_skill.py           Skill, SkillContext, SkillResult
│       ├── blackboard_state.py     état partagé typé (MutableMapping)
│       ├── primitives/             move_forward/backward, turn_left/right, stop_motion (+ base factorisée)
│       ├── perception/             detect_object, detect_obstacle, detect_red_ball (shim legacy)
│       └── behaviors/              follow_target (boucle fermée), move_circle
├── interfaces/
│   ├── intent_parser.py            Intent, IntentParser (regex FR/EN), IntentValidator
│   ├── language_controller.py      texte/intent → plan → exécution (priorité obstacle)
│   ├── robot_controller.py         adaptateur matériel : *_for(durée) avec arrêt obstacle/urgence
│   ├── perception_pipeline.py      ObjectDetection + Protocol ObjectPerceptionPipeline
│   └── voice_runtime.py            ★ point d'entrée : prompts LLM, expansions, retry, trace, CLI
└── hardware/
    ├── smart_car/smart_car.py      SmartCar2WD (gpiozero) + CLI
    ├── sensors/hc_sr04.py          capteur de distance
    ├── camera/                     camera_live_pipeline (thread), color_detector (HSV rouge/jaune), simulation
    └── audio/                      audio_utils (resolve_input_device), voice_assistant (legacy)
```

Points d'entrée CLI (`pyproject.toml`) : `voice-runtime` (**principal**), `voice-assistant` (legacy), `smart-car`, `hc-sr04`, `camera-live`, `color-detector` (alias `balle-rouge`), `test`.

---

## 3. Contrats de données

### 3.1 `Intent` (sortie attendue du LLM, après reconstruction)
```python
Intent(name: str, target: str|None, parameters: dict, confidence: float, raw_text: str)
```
Le LLM fournit : `intent` (ou `name`), `target`, `parameters`, `confidence` (clampée à [0,1]).

### 3.2 `SkillResult`
`status` (`success` | `failed` | `in_progress` | `timeout`), `message`, `data`, `confidence`, `next_action`.

### 3.3 Blackboard (état partagé)
Champs connus : `active_intent*`, `active_skill`, `camera_ready`, `target_object`, `last_object_position` (`left|center|right|UNKNOWN`), `last_object_distance_cm`, `obstacle_detected`, `close_enough`, `motion`, `follow_target_state`, `last_skill_result`, + `extra`.

### 3.4 Détection (`ObjectDetection`)
`label` (ex. `red_ball`, `yellow_object`), `position` (`left|center|right|UNKNOWN`), `distance_cm` (**toujours `None` avec la caméra actuelle**), `confidence`.

---

## 4. Catalogue des intents

`IntentValidator.ALLOWED_INTENTS` (liste blanche) :

| Intent | Skills planifiés (`INTENT_TO_SKILLS`) | Paramètres utiles | Remarques |
|---|---|---|---|
| `move_forward` | `move_forward` | `distance`+`unit`, **ou** `duration` | sans aucun des deux → mouvement **continu** (voir R1) |
| `move_backward` | `move_backward` | idem | pas d'arrêt obstacle sur le recul |
| `turn_left` / `turn_right` | idem | `angle` (+`unit:"degrees"`), **ou** `duration` | sans les deux → rotation **continue** |
| `stop` | `stop_motion` | — | |
| `follow_red_ball` | detect_object, follow_target, detect_obstacle, stop_motion | `target` doit être `null` ou `"red_ball"` | autre valeur → intent **rejeté** |
| `search_and_approach_object` | idem | `target_object` (`red`/`yellow`), `search`, `approach` | caméra : rouge et jaune seulement |
| `avoid_obstacle` | detect_obstacle, stop_motion, turn_left, move_forward | (ignore `speed`) | voir R3 |
| `contour_obstacle` | *(expansé par le runtime)* turn_right 45 → forward → turn_left 90 → forward → turn_right 45 | `clearance`, `unit`, `direction` | `direction` non exploité dans l'expansion |
| `spin_360` | *(expansé)* 4 × turn_right 90° | — | |
| `move_square` | *(expansé)* 4 × (forward `side` + turn 90°) | `side`/`distance`, `unit`, `turn_direction` | défaut 40 cm |
| `return_to_start` | *(expansé)* séquence inverse des mouvements **du même plan** | — | historique vide → n'émet rien |
| `execute_path` *(méta)* | *(expansé)* | `parameters.steps=[{action, distance?, unit?, angle?, duration?}]` | `action` ∈ {move_forward, move_backward, turn_left, turn_right, stop} ; non listé dans `ALLOWED_INTENTS` mais accepté car expansé avant validation |

Synonymes normalisés côté runtime : `contourner_obstacle`, `avoid`, `find_object`, `search_object`, `detect_object`, `approach_object`, `rotate_360`, `spin`, `square`, `path`, `trajectory`, `trajet`, `go_home`, `back_to_start`. Dans `execute_path`, `forward/move/backward/back/left/right` sont aussi acceptés.

**Non supportés** (aucun skill) : vitesse (`speed`, « vite », « lentement »), arc de cercle (`move_circle` existe mais n'est pas dans la liste blanche), cibles autres que rouge/jaune, conditions d'arrêt génériques, enchaînements conditionnels.

---

## 5. Pipeline d'exécution (`VoiceRuntime.handle_text_as_plan`)

1. Trace JSONL (`target/logs/runtime_trace_<horodatage>.jsonl`), `mission.reset()`.
2. Si `use_llm` : `ask_llm_for_intent_plan_with_trace` ; sinon `IntentParser().parse` (1 seul intent).
3. En cas d'exception, de JSON invalide, de `steps` vide/absent → **repli immédiat** sur `IntentParser` (un seul intent, pas de 2ᵉ timeout).
4. `_normalize_plan_intent_names` → `_expand_execute_path` → `_expand_high_level_intents` → `_expand_return_to_start`.
5. Plan tronqué à `max_plan_steps` (20) + `stop` ajouté.
6. `_validate_intent_plan` : étapes non autorisées **retirées** (erreurs journalisées) ; primitives **bornées** (`_sanitize_primitive_intent`).
7. Exécution : pour chaque intent, `_execute_intent_with_retry` (jusqu'à `max_step_retries`=2 → 3 tentatives) → `LanguageController.handle_intent`.
8. Statut final : `accepted` / `incomplete` / `aborted` ; état de mission ; trace.

Bornage des primitives : distance ∈ [0,1 ; 300] cm (ou [0,01 ; 3] m), angle ∈ [1 ; 360]°, durée ∈ [0,1 ; 12] s. **Seules les unités exactes `"m"` et `"cm"` sont reconnues** (tout autre texte est traité comme des cm).

`LanguageController.handle_intent` : avant chaque skill, injecte la perception live dans le blackboard ; si `check_obstacle()` est vrai avant `move_forward`/`turn_*`/`follow_target` → exécute `stop_motion` et **abandonne** (`aborted`, « obstacle prioritized »).

`follow_target` (boucle fermée, ~20 ms) : arrêt si obstacle, arrêt si cible perdue > 1 s, cible « atteinte » si `distance_cm ≤ 20` (jamais déclenché avec la caméra actuelle), timeout de suivi 8 s (statut `in_progress`), recherche par rotation vers la droite, alignement left/right par impulsions de 0,08 s, avance par impulsions de 0,12 s.

---

## 6. Les prompts actuels (dans `voice_runtime.py`)

Appel : `requests.post(LLM_URL, json=payload, timeout=(1.0, 4.0))`, non streamé, **sans `response_format`/grammaire**, modèle `"ministral-3-3b"`.

### 6.1 `SYSTEM_PROMPT` — intent unique (chemin `handle_text`, secondaire)
> Tu es un interprète de commande robotique. Réponds UNIQUEMENT en JSON valide avec les clés suivantes : intent, target, parameters, confidence. Les intents autorisées sont : follow_red_ball, search_and_approach_object, avoid_obstacle, move_forward, move_backward, turn_left, turn_right, stop.

Réglages : `temperature=0.2`, `max_tokens=256`.

### 6.2 `SYSTEM_PROMPT_PLAN` — plan multi-étapes (**chemin principal**)
> Tu es un planificateur de commandes robotiques. Tu reçois une instruction potentiellement composée. Réponds UNIQUEMENT en JSON valide au format: {"steps": [{"intent": str, "target": str|null, "parameters": object, "confidence": float}]}. Découpe la consigne en étapes atomiques ordonnées. Tu peux utiliser: (a) des intents atomiques (follow_red_ball, search_and_approach_object, avoid_obstacle, move_forward, move_backward, turn_left, turn_right, stop, return_to_start), ou (b) un intent execute_path avec parameters.steps=[{action, distance?, unit?, angle?, duration?}] où action est uniquement dans {move_forward, move_backward, turn_left, turn_right, stop}. Si la consigne contient un retour au point de départ, utilise explicitement return_to_start.

Réglages : `temperature=0.1`, `max_tokens=512`.

### 6.3 Lacunes constatées dans ces prompts
- **Aucun schéma de paramètres** : clés (`distance`, `unit`, `angle`, `duration`, `target_object`), unités autorisées, bornes, exclusivité distance/durée.
- **Aucune valeur de `target` imposée** (le validateur exige `null`/`"red_ball"` pour `follow_red_ball`).
- **Intents manquants** : `spin_360`, `move_square`, `contour_obstacle` (pourtant gérés par le runtime) ; absents aussi de `SYSTEM_PROMPT` : `return_to_start`.
- **Aucun exemple (few-shot)**, aucune règle pour l'entrée bruitée de Vosk, aucune règle pour les consignes **non supportées** (quel intent renvoyer ? aujourd'hui rien de défini).
- **Aucune consigne de concision** alors que le débit du modèle est très faible sur Pi (voir §7).
- **Pas de mode JSON contraint** : on compte sur le prompt + nettoyage des backticks.

---

## 7. Contraintes à respecter pour écrire les prompts

### 7.1 Modèle et latence
- Modèle 3B quantisé, CPU seul. L'audit v5 annonce **3–6 tokens/s** sur Pi 5 (mesure non vérifiée de mon côté).
- Génération **non streamée** avec **timeout de lecture = 4 s** : tout ce qui n'est pas fini en ~4 s (évaluation du prompt **+** génération) déclenche le repli sur le parseur regex. À 3–6 tok/s, cela laisse seulement ~12–24 tokens de sortie. **Un plan JSON multi-étapes verbeux sortira presque toujours du budget sur le Pi** (sur Mac c'est sans doute différent).
- Conséquences pour les prompts : **sortie la plus compacte possible** (clés courtes, pas d'espaces inutiles, pas de champ superflu comme `confidence` si on peut le remplir côté code), **system prompt court** (le temps d'évaluation du prompt est linéaire) et **statique** (placé en tête, texte utilisateur en dernier) pour profiter du cache de préfixe de `llama.cpp` (`cache_prompt`, **à vérifier** selon la version du serveur).
- `--ctx-size` : `install_llm.sh` met 2048 ; l'audit v5 parle de 4096 → incohérence documentaire.

### 7.2 Entrée : transcription Vosk (`vosk-model-small-fr-0.22`)
- Texte en minuscules, sans ponctuation fiable, erreurs de reconnaissance fréquentes avec un petit modèle.
- **(à vérifier sur des traces réelles)** les nombres arrivent probablement **en toutes lettres** (« cinquante centimètres », « quarante-cinq degrés »). Les regex du parseur local ne comprennent **que les chiffres** → le prompt doit demander au LLM de **convertir en chiffres**.

### 7.3 Sortie : ce que le code accepte réellement
- JSON objet ; backticks ```json tolérés.
- Si `parameters` ou un `step` n'est pas un `dict` → exception → **tout le plan est abandonné** pour le repli regex.
- `target` pour `follow_red_ball` : exactement `null` ou `"red_ball"` (sinon étape retirée).
- `target`/`target_object` pour `search_and_approach_object` : la caméra ne sait détecter que **rouge** et **jaune** ; la correspondance se fait par sous-chaîne dans le label (`red`, `yellow`, `red_ball`…). `"rouge"`, `"balle"`, `"bouteille"` ne matchent pas.
- Unités : `"cm"`/`"m"` pour les distances, `"degrees"` pour les angles.
- Si `duration` est fournie en plus de `distance`/`angle`, **`duration` l'emporte**.
- Les paramètres `speed`/vitesse sont **ignorés** par les skills.

### 7.4 Règles de hiérarchie (décisions du projet, `specs/03`)
- LLM = interprète + planificateur de haut niveau ; **jamais** de GPIO, jamais de texte libre, sécurité dans le runtime.
- Whitelist d'actions, bornes strictes, fallback local immédiat.

---

## 8. Calibration et réglages

`config/runtime_calibration.toml` (prioritaire sur les défauts du code) :

| Clé | TOML | Défaut `settings.py` | Défaut `calibration_helpers.py` |
|---|---|---|---|
| `cm_per_second` | **65.0** | 25.0 | 25.0 |
| `deg_per_second` | **360.0** | 360.0 | 180.0 |
| `turn_speed` | 0.5 | 0.5 | — |
| `step_timeout_seconds` | 6.0 | 6.0 | — |
| `mission_timeout_seconds` | 45.0 | 45.0 | — |
| `max_step_retries` | 2 | 2 | — |
| `max_plan_steps` | 20 | 20 | — |
| `max_distance_cm` | 300 | 300 | — |
| `max_angle_deg` | 360 | 360 | — |
| `max_duration_sec` | 12 | 12 | — |

Conversions **en boucle ouverte** : `durée = distance / cm_per_second` ; `durée = angle / deg_per_second` (rotation à `turn_speed` 0,5). Ex. 90° → 0,25 s ; 50 cm → ~0,77 s. Aucun encodeur/IMU dans le code.

Matériel : IN1–IN4 = GPIO 5, 6, 16, 24 ; ENA/ENB (PWM) = GPIO 12, 13 ; HC-SR04 trigger = GPIO 17, echo = GPIO 27 (BCM) ; seuil d'obstacle 20 cm ; vitesse au démarrage du runtime 0,5.

---

## 9. Constats et risques (priorisés)

Gravité : 🔴 sécurité/comportement physique · 🟠 fonctionnel · 🟡 maintenance.

### 🔴 R1 — Mouvement continu sans arrêt quand les paramètres manquent
`BaseMotionPrimitiveSkill._execute_motion` appelle `forward()`/`left()`… **sans durée** si ni `duration` ni `distance`/`angle` ne sont fournis, et `_sanitize_primitive_intent` n'injecte aucun défaut. Un plan LLM `{"intent":"move_forward","parameters":{}}` (très plausible pour « avance ») fait rouler le robot **indéfiniment**, sans surveillance d'obstacle (le contrôle n'existe que dans les variantes `*_for`). Le parseur local, lui, met `duration=1.0` par défaut pour avancer/reculer.
→ **Prompt** : exiger systématiquement `distance`+`unit` ou `duration` (ou `angle`). → **Code** : défaut de durée dans la sanitization + `stop` garanti en fin de mission (`try/finally`).

### 🔴 R2 — Aucun `stop` garanti en fin de plan
`close()` n'arrête le robot qu'à l'extinction du runtime. Après une mission, un mouvement continu (R1, `move_circle`, `avoid_obstacle`) continue.

### 🔴 R3 — Les rotations sont bloquées par l'obstacle frontal
`RobotController.left_for/right_for` s'interrompent si `check_obstacle()` est vrai, et `LanguageController` abandonne avant tout `turn_*` si un obstacle est détecté. Un robot à < 20 cm d'un obstacle **ne peut plus pivoter pour s'en écarter** : `avoid_obstacle` et `contour_obstacle` échouent précisément dans le cas pour lequel ils existent. De plus, `avoid_obstacle` n'a aucun paramètre (angle/durée) → rotation + avance **continues** (R1).

### 🔴 R4 — Capteur d'obstacle « fail-open » à l'initialisation
`build_hardware_runtime` crée `SmartCar2WD(require_obstacle_sensor=False)` : si le capteur est absent, `check_obstacle()` renvoie `False` en silence. Si la voiture ne s'initialise pas, l'exception est avalée (`robot=None`) sans log. (En lecture, en revanche, le capteur est bien « fail-safe » : mesure absente ⇒ obstacle.)

### 🟠 R5 — Une étape en échec n'interrompt pas la mission
La boucle d'exécution de `handle_text_as_plan` enregistre l'échec mais **continue** les étapes suivantes (seul le timeout de mission fait `break`). Combiné au retrait silencieux des étapes invalides (§5.6), un plan partiel peut s'exécuter (ex. « avance, fais un salto, recule » → avance + recule).

### 🟠 R6 — Le timeout d'étape est a posteriori et contredit les autres réglages
`step_timeout_seconds` (6 s) est testé **après** l'exécution : une étape réussie mais longue est marquée `aborted`. Or `follow_target` peut durer 8 s et `max_duration_sec` autorise 12 s → un `move_forward` de 10 s ou un suivi complet sont déclarés `aborted` alors qu'ils ont abouti.

### 🟠 R7 — Distances et angles perdus en repli sur le parseur local
`IntentParser` n'extrait ni distance ni angle pour avance/recul/rotation (seulement `duration`, défaut 1 s ; angle fixe 90°). Or, sur Pi, le LLM va souvent expirer (§7.1) → « avance de 50 cm » devient « avance 1 s ». Seul le chemin LLM porte ces informations (hors `move_square`/`contour_obstacle` où le parseur extrait une distance).

### 🟠 R8 — La caméra ne fournit pas de distance
`distance_cm` est toujours `None` → la condition « cible atteinte » de `follow_target` ne se déclenche jamais ; la fin dépend de l'obstacle HC-SR04 (20 cm) ou du timeout de 8 s. De plus `_iter_colors_for_target(None, …)` ignore la cible demandée et scanne toujours rouge + jaune ; l'objet est filtré ensuite par sous-chaîne du label.

### 🟠 R9 — Incohérences de la voie « legacy » `LanguageController.handle_text`
`handle_text` s'arrête après la 1ʳᵉ skill qui renvoie un `next_action` (quasi toutes les primitives renvoient `"track_target"`), donc `move_square` n'exécute qu'un avance ; `spin_360` planifie 4 × `turn_right` avec `angle=360` chacun. Cette voie est testée mais **non utilisée** par `handle_text_as_plan`. `handle_text` et `handle_intent` dupliquent leur code.

### 🟠 R10 — `return_to_start`
Autorisé par le validateur mais sans entrée dans `INTENT_TO_SKILLS` (rejeté en voie directe) ; en voie plan, il est expansé en inversant **uniquement** les mouvements du plan courant (pas de mémoire entre commandes, pas d'odométrie).

### 🟡 R11 — `MoveCircleSkill`
Appelle `left()` puis `forward()` : le second écrase le premier (commande moteur « dernier gagnant ») ; `move_circle` n'est pas dans la liste blanche, donc inatteignable par la voix.

### 🟡 R12 — Dérives de documentation
- `docs/audit-v5` décrit **ROS2, PCA9685, encodeurs en quadrature, balises AruCo, Whisper, migration Qwen 1.5B** : rien de cela n'existe dans le code (Vosk, GPIO direct, Ministral 3B). Traiter ses chiffres de performance comme **non vérifiés**.
- `PROJECT_CONTEXT.md` cite `docs/audit-architecture-2026.md` (le fichier est désormais dans `docs/audit-v*/`), liste les chantiers P1–P5 comme non cochés alors que des fiches existent, et sa section « 3) Restant » est tronquée dans le dump.
- `README` recommande `uv run voice-assistant` (legacy) alors que le point d'entrée actuel est `voice-runtime`.
- Indentation : tabulations dans `settings.py`, 4 espaces ailleurs ; `calibration_helpers.py` semble inutilisé (dupliqué par `base_motion_primitive.py`).

---

## 10. Pistes pour les prompts (à valider avec toi)

1. **Un contrat de sortie compact et strict** — par exemple :
   `{"steps":[{"i":"<intent>","t":<target|null>,"p":{...}}]}` (le code accepte aujourd'hui `intent`/`name`, `target`, `parameters`, `confidence` ; adopter des clés courtes demanderait un petit changement de parsing). `confidence` pourrait être calculée côté code pour économiser des tokens.
2. **Activer le JSON contraint** côté serveur (`response_format: {"type":"json_object"}` ou grammaire GBNF) au lieu de se reposer sur le prompt seul — cela supprime la classe d'erreurs « JSON invalide → repli ».
3. **Lister les 12 intents + `execute_path`** avec, pour chacun, les paramètres exacts et leurs unités (`cm`/`m`, `degrees`), en précisant : « distance **ou** durée, jamais aucune ».
4. **Règles d'entrée Vosk** : convertir les nombres en chiffres, ignorer les mots parasites, tolérer les fautes de transcription proches.
5. **Cibles** : `follow_red_ball` → `target:"red_ball"` ; `search_and_approach_object` → `target_object` ∈ {`"red"`, `"yellow"`, `null`}.
6. **Consignes non supportées** : définir un comportement explicite (ex. un intent `unknown` ou une liste vide) plutôt que d'inventer un intent ; rappeler qu'aucune vitesse n'est pilotable.
7. **3 à 6 exemples courts** (few-shot) couvrant : commande simple, commande composée, distance en mètres, angle, « tourne jusqu'à voir X », retour au point de départ, consigne hors périmètre.
8. **Brièveté** : prompt système court et identique à chaque appel, sortie minimale (voir §7.1), `max_tokens` ajusté (aujourd'hui 256/512, très au-delà de ce que le timeout permet).
9. **Jeu d'évaluation** : réutiliser `scripts/test/run_runtime_standard_scenarios_mac.sh` + `replay_runtime_trace_mac.sh` et les traces JSONL pour comparer plusieurs versions de prompt (taux de JSON valide, intents corrects, temps de réponse).

---

## 11. Commandes utiles

```bash
uv sync --project .
pytest                                              # ~42 tests (unit + intégration LLM)
bash scripts/test/run_llm_runtime_mac.sh --text "va vers la balle rouge"
bash scripts/test/run_llm_runtime_mac.sh --stop
bash scripts/test/run_mission_mac.sh
bash scripts/test/replay_runtime_trace_mac.sh
uv run voice-runtime [--once] [--no-llm] [--input-device auto|bluetooth|wm8960|default]
uv run smart-car forward --duration 1
sudo systemctl start ministral.service && curl http://127.0.0.1:8080/v1/models   # sur le Pi
```

Fichiers de contexte à garder cohérents : `PROJECT_CONTEXT.md` (document vivant, règle de maintenance §16), `.github/copilot-instructions.md` (mode concis : diffs seulement, 1 question max, `/cp` = commit conventionnel + push).

---

## 12. Questions ouvertes

- Les prompts doivent-ils viser **le Pi 5 en conditions réelles** (timeout 4 s, 3B) ou d'abord le Mac (confort) ? Cela change le budget de tokens.
- Souhaites-tu **modifier le code** associé (défauts de durée, `stop` final, JSON contraint, timeout/streaming) ou **rester strictement sur les prompts** ?
- Disposes-tu de **traces réelles** (`target/logs/*.jsonl`) de transcriptions Vosk pour confirmer le format des nombres ?
- Faut-il élargir le vocabulaire (autres couleurs, vitesse, `move_circle`) ou le figer ?
