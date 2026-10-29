# Prompts GitHub Copilot — use case « balle jaune »

**Cible :** « cherche la balle jaune, approche-toi à 1 m de la balle jaune puis suis-la pendant 5 min quand elle se déplace ».

**Mode d'emploi**
- Un prompt = une étape = un commit. Ne passe à la suivante que si `pytest` est vert.
- Colle chaque bloc dans Copilot Chat (mode **Agent**/Edits si dispo), avec `REFERENCE_IROBOT.md` et `PROJECT_CONTEXT.md` ouverts ou ajoutés au contexte (`#file`).
- Copilot suit déjà `.github/copilot-instructions.md` (diffs, concis, 1 question max) : les prompts ci-dessous n'ont donc pas besoin de le répéter.
- Étapes 1 à 9 : **sans matériel** (Mac, `FakeRobot`). Test réel sur Pi uniquement à l'étape 10.

**Ordre**

| # | Étape | Pourquoi d'abord |
|---|---|---|
| 0 | Préambule de contexte | cadre commun |
| 1 | Sécurité de base | un robot qui ne s'arrête pas est le pire risque |
| 2 | Réglages et timeouts | 5 min est incompatible avec les plafonds actuels |
| 3 | Estimation de distance | sans distance, « à 1 m » est impossible |
| 4 | Recherche + approche à distance cible | corrige aussi la recherche qui abandonne après 1 s |
| 5 | Nouveau skill `follow_object` | suivi à distance constante pendant N secondes |
| 6 | Câblage intent/parseur/planner | rend la commande atteignable |
| 7 | Arrêt d'urgence vocal | boucle de 5 min = robot sourd sinon |
| 8 | Prompt LLM + repli | le LLM doit produire le bon plan, vite |
| 8b | Corrections LLM après mesures | stop sans LLM, timeout, schéma JSON |
| 8c | Diagnostic LLM et démarrage à froid | traces de latence, attente du préchauffage, format de sortie réglable |
| 9 | Test de scénario complet | verrouille le comportement |
| 10 | Doc, essai sur Pi, commit | |
| 11 | Nettoyage : scripts d'installation, scripts Mac, doc | à faire quand le use case fonctionne |

---

## Prompt 0 — Préambule (à coller une fois, en début de session)

```
Contexte : projet Python `irobot` (src/irobot, tests/, config/runtime_calibration.toml) pour un robot Raspberry Pi. Lis REFERENCE_IROBOT.md et PROJECT_CONTEXT.md avant toute modification.

Objectif global : permettre la commande vocale « cherche la balle jaune, approche-toi à 1 m puis suis-la pendant 5 min ». Je te donnerai les étapes une par une.

Règles pour toute la session :
- Le LLM ne pilote jamais le matériel : tout passe par Intent -> validation/bornage -> Skills -> RobotController.
- Aucune régression : `pytest` doit rester vert (≈42 tests) ; ajoute des tests unitaires pour chaque comportement nouveau, avec FakeRobot (tests/unit/fake_robot.py) et sans matériel.
- Pas de `time.sleep` long dans les tests : rends l'horloge injectable (time_fn / sleep_fn) quand une boucle dépend du temps.
- Python >= 3.12, indentation 4 espaces (convertis les tabulations si tu touches settings.py).
- Réponds avec des diffs uniquement.

Réponds seulement « OK » pour confirmer.
```

---

## Prompt 1 — Sécurité de base

```
Étape 1/10 — Sécurité. Fichiers : src/irobot/interfaces/voice_runtime.py, src/irobot/domain/skills/primitives/base_motion_primitive.py, src/irobot/interfaces/language_controller.py.

Problèmes à corriger :
1. Une primitive move_forward/move_backward/turn_left/turn_right sans `duration` ni `distance` ni `angle` appelle forward()/left()… en continu, sans arrêt. Dans `_sanitize_primitive_intent` (voice_runtime.py), injecte une durée par défaut : 1.0 s pour avance/recul, et pour les rotations un angle par défaut de 90° si ni angle ni duration. La durée finale reste bornée par max_duration_sec.
2. Les unités : seules "m" et "cm" sont reconnues, tout autre texte est traité comme des cm. Normalise avant : {"m","meter","meters","metre","metres","mètre","mètres"} -> "m" ; {"cm","centimeter","centimeters","centimetre","centimetres","centimètre","centimètres"} -> "cm" ; unité inconnue -> "cm". Applique aussi dans base_motion_primitive._resolve_motion_parameters.
3. Aucun stop garanti en fin de mission : dans `VoiceRuntime.handle_text_as_plan`, entoure l'exécution des étapes d'un try/finally qui appelle `self.robot.stop()` (en ignorant les exceptions) quel que soit le résultat.
4. La boucle d'exécution continue après une étape en échec. Après une étape dont le statut est "rejected", "failed", "incomplete" ou "aborted", fais un `break` : les étapes suivantes ne s'exécutent pas, le statut global reste cohérent avec le code existant.
5. Dans `_validate_intent_plan`, si au moins une étape a été rejetée, rejette tout le plan (status "rejected", reason "invalid plan step") au lieu d'exécuter un plan partiel. Garde `validation_errors` dans la réponse et la trace.

Tests à ajouter (tests/unit/test_voice_runtime.py) : durée par défaut injectée ; "mètres" -> "m" ; stop appelé en fin de mission même après exception ; arrêt des étapes après un échec ; rejet complet d'un plan contenant une étape invalide. Adapte les tests existants qui supposaient un plan partiel, en le signalant.
```

---

## Prompt 2 — Réglages et timeouts

```
Étape 2/10 — Réglages. Fichiers : src/irobot/config/settings.py, config/runtime_calibration.toml, src/irobot/interfaces/voice_runtime.py, tests/unit/test_runtime_settings.py.

Contexte : step_timeout_seconds=6 est vérifié APRÈS l'exécution et marque "aborted" une étape réussie mais longue ; mission_timeout_seconds=45 et max_duration_sec=12 empêchent un suivi de 5 min.

À faire :
1. Dans RuntimeSettings + chargeur TOML, ajoute (avec valeurs par défaut et lecture dans [limits] / [runtime]) :
   - max_follow_duration_sec = 600.0
   - min_stand_off_cm = 30.0 ; max_stand_off_cm = 300.0
   - search_timeout_seconds = 25.0  (temps max de recherche d'une cible)
   - timeout_margin_seconds = 10.0
   Mets les mêmes clés dans config/runtime_calibration.toml. Unifie aussi le défaut cm_per_second de settings.py avec la valeur du TOML (65.0) ; signale tout test impacté.
2. Dans voice_runtime.py, calcule un timeout effectif par étape : `max(step_timeout_seconds, duration_s + search_timeout_seconds + timeout_margin_seconds)` quand l'intent porte `parameters["duration_s"]` (sinon le timeout actuel). Utilise-le dans `_execute_intent_with_retry`.
3. Calcule un timeout de mission effectif : `max(mission_timeout_seconds, somme des timeouts effectifs des étapes)`.
4. Pas de retry quand l'étape s'est terminée par un statut "aborted" ou par dépassement de timeout (aujourd'hui seuls "failed"/"in_progress" sont retentés ; garde ce comportement).

Tests : chargement TOML des nouvelles clés, valeurs par défaut sans fichier, calcul du timeout effectif avec et sans duration_s.
```

---

## Prompt 3 — Estimation de distance de la balle

```
Étape 3/10 — Perception : distance. Fichiers : src/irobot/hardware/camera/color_detector.py, camera_live_pipeline.py, src/irobot/interfaces/perception_pipeline.py, config/runtime_calibration.toml.

Contexte : CameraLivePerceptionPipeline renvoie toujours ObjectDetection.distance_cm = None. La frame est tournée de 90° (cv2.rotate) avant la détection ; la caméra capture en 640x480.

À faire :
1. Lis color_detector.py et indique (en commentaire de PR) quelles infos géométriques sont disponibles pour chaque candidat (rayon, bbox, aire). Si elles ne sont pas remontées jusqu'à `choose_best_result`, fais-les remonter sans casser l'API publique existante (les chaînes "BALL_YELLOW_A_GAUCHE" doivent rester inchangées pour les tests existants ; ajoute une variante qui renvoie aussi les métriques).
2. Ajoute `diameter_px: float | None = None` à ObjectDetection. Calcule-le de façon invariante à la rotation (diamètre du cercle équivalent via cv2.minEnclosingCircle ou sqrt(4*aire/pi)), PAS la largeur de bbox.
3. Crée src/irobot/hardware/camera/distance_estimator.py avec une fonction pure `estimate_distance_cm(diameter_px, ball_diameter_cm, focal_px) -> float | None` (modèle sténopé : d = focal_px * ball_diameter_cm / diameter_px ; None si diameter_px <= 0).
4. Ajoute une section [camera] dans runtime_calibration.toml : ball_diameter_cm (défaut 6.5), focal_px (défaut 600.0, à calibrer), et expose-les dans RuntimeSettings.
5. Dans CameraLivePerceptionPipeline, renseigne `distance_cm` via estimate_distance_cm. Applique un lissage (moyenne glissante sur les 3-5 dernières mesures, ou filtre exponentiel alpha=0.4) pour limiter le bruit.
6. Fusion optionnelle avec le capteur HC-SR04 : si le robot expose `read_distance_cm()` et que la balle est au centre, et que la mesure ultrason est dans ±25 % de l'estimation visuelle, retourne la mesure ultrason ; sinon garde l'estimation visuelle. Cette fusion doit être injectable (paramètre du constructeur) et désactivable.
7. Ajoute un petit script CLI `calibrate-distance` (entrée dans pyproject.toml, sous irobot.hardware.camera) qui affiche en direct diameter_px et distance estimée, et un mode `--known-distance-cm 100` qui affiche le focal_px à reporter dans le TOML.

Tests (sans caméra) : estimate_distance_cm (valeurs connues, entrée invalide), lissage, fusion ultrason (cas concordant, cas divergent, capteur absent), TOML.
```

---

## Prompt 4 — Recherche réelle + approche à distance cible

```
Étape 4/10 — Recherche et approche. Fichier : src/irobot/domain/skills/behaviors/follow_target.py (+ tests/unit/test_skills_behaviors.py).

Constats : (a) `follow_target` abandonne après `max_target_loss_s` = 1 s sans cible, y compris au tout début : la phase « cherche » ne tourne donc que ~1 s. (b) la condition « cible atteinte » existe (distance_cm <= approach_threshold_cm) mais n'a jamais de distance avec la caméra actuelle (réglé à l'étape 3). (c) les rotations de recherche se font toujours vers la droite.

À faire :
1. Sépare deux phases dans FollowTargetSkill : SEARCH (cible jamais vue ou perdue) et TRACK (cible visible). En SEARCH, le budget est `search_timeout_s` (paramètre d'intent, défaut settings.search_timeout_seconds) au lieu de `max_target_loss_s`. Si le budget est épuisé sans cible : status "failed", data["target_lost"]=True, robot arrêté.
2. En SEARCH, effectue un balayage : rotation par impulsions dans un sens, en gardant le sens de la dernière position connue (left/right) si elle existe, sinon la droite.
3. Accepte le paramètre `stand_off_cm` comme synonyme de `approach_threshold_cm` (priorité à `approach_threshold_cm` s'il est fourni). Borne-le entre min_stand_off_cm et max_stand_off_cm (settings).
4. Ajoute `stand_off_tolerance_cm` (défaut 10) : la cible est « atteinte » quand distance_cm <= stand_off_cm + tolerance. Pendant l'approche, l'avance se fait par impulsions plus courtes quand distance_cm est proche (ex. < 2 x stand_off) pour éviter de dépasser.
5. Rends l'horloge injectable (time_fn, sleep_fn en attributs de classe ou paramètres du constructeur avec défauts time.monotonic / time.sleep) pour des tests rapides.
6. Garde la compatibilité du chemin non-live (sans perception.detect) et les tests existants.

Tests : recherche qui aboutit après N impulsions ; recherche épuisée -> failed ; balle à droite/gauche -> alignement ; stand_off 100 cm atteint avec distances simulées décroissantes ; obstacle -> arrêt de sécurité ; budget de recherche distinct du budget de perte de cible.
```

---

## Prompt 5 — Nouveau skill `follow_object` (suivi à distance constante)

```
Étape 5/10 — Suivi à distance constante. Nouveau fichier : src/irobot/domain/skills/behaviors/follow_object.py ; enregistre-le dans behaviors/__init__.py, domain/skills/__init__.py et SkillRegistry.default().

Skill `FollowObjectSkill` (name="follow_object") : suit une cible visuelle en conservant une distance cible pendant une durée donnée.

Paramètres lus dans context.state["active_intent_parameters"] : target_object (défaut "yellow"), stand_off_cm (défaut 100, borné settings), stand_off_tolerance_cm (défaut 15), duration_s (défaut 60, borné par max_follow_duration_sec), max_target_loss_s (défaut 3.0), search_timeout_s (défaut settings.search_timeout_seconds).

Comportement (boucle ~20-50 ms, horloge injectable comme à l'étape 4) :
- Chaque tour : vérifier arrêt d'urgence (robot.is_emergency_stop_requested si disponible, voir étape 7) et obstacle (check_obstacle) -> arrêt et status "success" avec data["obstacle_detected"]=True (cohérent avec follow_target).
- Lire la détection : position (left/center/right) et distance_cm.
- Alignement d'abord : si left/right -> impulsion de rotation courte du bon côté, puis tour suivant.
- Régulation de distance quand centré : distance > stand_off + tolérance -> impulsion avant (durée proportionnelle à l'écart, bornée 0,05–0,25 s) ; distance < stand_off - tolérance -> impulsion arrière (courte, 0,05–0,15 s, car aucun capteur arrière) ; sinon -> robot arrêté (zone morte).
- Perte de cible : arrêter le robot ; si perdue depuis plus de max_target_loss_s, passer en recherche (même logique de balayage que follow_target, extraire une fonction/mixin partagé pour éviter la duplication) pendant search_timeout_s ; si retrouvée -> reprendre le suivi ; sinon -> status "failed", data["target_lost"]=True.
- Fin normale à duration_s : arrêter le robot, status "success", data = {iterations, duration_s, final_distance_cm, reacquisitions}.
- Toute exception -> arrêter le robot puis SkillResult failed (comme les autres skills).
- Ne jamais laisser le robot en mouvement en sortant (try/finally -> stop).
- Met à jour context.state["follow_target_state"] avec la phase (aligning/approaching/holding/backing/searching).

Tests (horloge simulée, perception simulée qui déplace la balle) : maintien à 100 cm, balle qui s'éloigne -> avance, balle qui se rapproche -> recule, zone morte -> pas de mouvement, perte puis retrouvaille, perte définitive -> failed, obstacle -> arrêt, fin à duration_s, stop garanti sur exception.
```

---

## Prompt 6 — Câblage : intents, parseur, validation, planner, runtime

```
Étape 6/10 — Câblage de follow_object. Fichiers : src/irobot/interfaces/intent_parser.py, src/irobot/domain/orchestrator/planner.py, src/irobot/interfaces/voice_runtime.py, src/irobot/interfaces/language_controller.py, config/runtime_calibration.toml.

À faire :
1. IntentValidator.ALLOWED_INTENTS : ajoute "follow_object". Règle de validation : target ∈ {"red","yellow", None} ; sinon rejeté.
2. SkillPlanner.INTENT_TO_SKILLS["follow_object"] = ["follow_object"].
3. voice_runtime.py : ajoute une sanitization des paramètres de "search_and_approach_object" et "follow_object" : stand_off_cm borné [min_stand_off_cm, max_stand_off_cm], duration_s borné [1, max_follow_duration_sec], search_timeout_s borné [1, 120], valeurs non numériques -> défauts. Appelle-la dans _validate_intent_plan comme pour les primitives.
4. Normalisation des noms (_normalize_plan_intent_names) : ajoute les synonymes "follow", "track", "track_object", "follow_target", "suivre", "suit" -> "follow_object".
5. Normalisation de target : "jaune","yellow","balle jaune","yellow_ball" -> "yellow" ; "rouge","red","balle rouge","red_ball" -> "red" pour follow_object et search_and_approach_object (garde "red_ball" tel quel pour follow_red_ball).
6. IntentParser (repli local sans LLM) : 
   - `_extract_duration` doit aussi comprendre les minutes ("5 min", "5 minutes", "cinq minutes" si possible avec un petit dictionnaire de nombres français 0-20 + dizaines) et les convertir en secondes pour `duration_s` (ne casse pas l'actuel `duration` des primitives).
   - `_extract_distance` : reconnaître « à 1 m », « à un mètre », « à 50 cm » dans un contexte d'approche et le mettre dans `stand_off_cm` (convertir m -> cm).
   - Reconnaître « suis », « suit », « suivre » -> intent "follow_object" avec target (yellow/red) + duration_s + stand_off_cm.
   - Une phrase composée (« cherche …, approche-toi …, puis suis-la … ») : ajoute une méthode `parse_plan(text) -> list[Intent]` qui découpe sur « puis », « ensuite », « et puis », « , » et applique `parse` à chaque segment, en reportant le target d'un segment précédent aux segments qui disent « la/le/-la ». Utilise-la comme repli dans ask_llm_for_intent_plan_with_trace à la place de [IntentParser().parse(text)].
7. Garde `return_to_start`, `spin_360` etc. inchangés.

Tests : parser sur « cherche la balle jaune, approche toi à 1m de la balle jaune puis suit la pendant 5 min » -> [search_and_approach_object(yellow, stand_off_cm=100), follow_object(yellow, stand_off_cm=100, duration_s=300)] ; variantes (« cinq minutes », « 2 mètres », rouge) ; validateur ; sanitization ; plan complet exécuté via VoiceRuntime avec FakeRobot et perception simulée (sans LLM : use_llm=False).
```

---

## Prompt 7 — Arrêt d'urgence (robot « sourd » pendant 5 min)

```
Étape 7/10 — Arrêt d'urgence. Fichiers : src/irobot/interfaces/robot_controller.py, src/irobot/interfaces/voice_runtime.py, follow_target.py, follow_object.py.

Problème : pendant un suivi de 5 min, la boucle est synchrone et le runtime n'écoute plus ; impossible de dire « stop ».

À faire :
1. RobotController : ajoute un `threading.Event` interne ; méthodes `request_emergency_stop()` (set + stop()) et `clear_emergency_stop()` ; et `is_emergency_stop_requested()` qui retourne True si l'événement est levé OU si le robot sous-jacent expose l'un des détecteurs déjà gérés par `_is_emergency_stop_requested`. Fais en sorte que `_is_emergency_stop_requested` prenne en compte l'événement interne.
2. Les skills follow_target et follow_object testent `context.robot.is_emergency_stop_requested()` (si la méthode existe) à chaque tour de boucle, et sortent proprement : robot arrêté, status "aborted" (ou "success" avec data["emergency_stop"]=True, choisis la cohérence avec le code existant et documente-la).
3. VoiceRuntime : exécute `handle_text_as_plan` dans un thread de travail (daemon) pendant que le thread principal continue à lire la transcription Vosk. Si une nouvelle phrase transcrite est reconnue comme « stop/arrête/arrête-toi/halte/pause » (IntentParser(name="stop")), appelle `robot.request_emergency_stop()` immédiatement ; toute autre phrase reçue pendant une mission est ignorée avec un message, sauf après la fin de la mission. Au démarrage d'une nouvelle mission, appelle clear_emergency_stop().
4. Ctrl+C / `close()` : lève l'arrêt d'urgence, attend le thread de travail (timeout 2 s) et arrête le robot.
5. Garde un chemin synchrone (paramètre `threaded=False`) pour les tests et `--once`.

Tests : le stop demandé depuis un autre thread interrompt un follow_object en cours (horloge simulée) ; flag effacé au démarrage d'une mission ; une phrase non-stop est ignorée pendant la mission ; close() arrête le robot.
```

---

## Prompt 8 — Prompt LLM (Qwen2.5-1.5B) + prétraitement + appel serveur

Avant de donner ce prompt à Copilot : mets `eval_prompt_plan.py` dans `scripts/test/` du dépôt (Copilot s'en inspire pour le prétraitement) et lance-le sur ton Mac, puis sur le Pi, pour valider le prompt système et mesurer la latence.

**À jouer AVANT le 8b.** Le 8b s'appuie sur ce que le 8 met en place (prétraitement des nombres, nouveau prompt système, modèle configurable) et le complète (schéma JSON, timeout 8 s, gardes). Le test `eval_prompt_plan.py` envoie directement les requêtes au serveur : il ne vérifie pas que le code du dépôt a été modifié. Si Copilot constate que certains points sont déjà faits (modèle configurable, migration de la config), il les saute. Les points 4 (`response_format`, `max_tokens`) et 8 (`steps` vide) sont repris et améliorés par le 8b : applique-les quand même, le 8b les remplacera.

```
Étape 8/10 — LLM local : migration vers Qwen2.5-1.5B-Instruct + prompt + prétraitement. Fichiers : src/irobot/interfaces/voice_runtime.py, src/irobot/config/settings.py, scripts/install_llm.sh (et l'unité systemd), README.md, PROJECT_CONTEXT.md, specs/03_llm_model_strategy.md, tests/unit/test_voice_runtime.py. Référence : scripts/test/eval_prompt_plan.py (fonctions fr_numbers_to_digits et preprocess, prompt système).

Contraintes : modèle 1,5B quantisé sur Raspberry Pi 5, appel non streamé, timeout de lecture 4 s. Un petit modèle suit mal les consignes longues et convertit mal les nombres en lettres : on lui donne donc une entrée DÉJÀ normalisée, un prompt court et statique, et une sortie JSON minimale. Le repli local reste le filet de sécurité.

À faire :
1. Prétraitement déterministe (nouveau module src/irobot/interfaces/text_normalizer.py) : porte `fr_numbers_to_digits` et `preprocess` depuis eval_prompt_plan.py sans changer leur comportement (nombres français en lettres -> chiffres ; « N minutes » -> « N*60 secondes » ; « N mètres » -> « N*100 centimètres » ; « un/une » converti seulement devant une unité de mesure). Applique `preprocess` au texte envoyé au LLM, dans ask_llm_for_intent_plan_with_trace ET ask_llm_for_intent. Réutilise-le aussi dans IntentParser (repli local) pour que « cinquante centimètres » soit compris sans LLM ; garde `raw_text` d'origine dans les Intent et la trace (ajoute le texte prétraité sous `normalized_text`).
2. Remplace SYSTEM_PROMPT_PLAN par le contenu exact du prompt système de eval_prompt_plan.py (même nom de constante). Aligne SYSTEM_PROMPT (intent unique) sur la même liste d'intents, sans exemples multiples et avec le format de sortie actuel.
3. Modèle configurable : LLM_MODEL lu depuis la variable d'environnement LLM_MODEL (défaut "qwen2.5-1.5b") et utilisé dans les deux payloads, à la place de "ministral-3-3b".
4. Dans les deux appels requests.post : ajoute "response_format": {"type": "json_object"} et "cache_prompt": true ; max_tokens = 160 pour le plan et 96 pour l'intent unique ; temperature = 0.0. En cas d'erreur HTTP 400, refais l'appel une fois sans response_format (commentaire : dépend de la version de llama-server).
5. Robustesse : si `parameters` ou une étape n'est pas un dict, ignore seulement CETTE étape (pas tout le plan) ; `confidence` absente -> 0.8. Une étape sans `unit` est traitée en cm (vérifie que c'est déjà le cas et ajoute un test).
6. Rends LLM_CONNECT_TIMEOUT_SECONDS, LLM_READ_TIMEOUT_SECONDS et les max_tokens configurables par variables d'environnement (défauts 1.0 / 4.0 / 160).
7. Préchauffage du serveur au démarrage (requête minimale avec le prompt système, en arrière-plan, sans bloquer) pour remplir le cache de prompt.
8. Distingue « hors périmètre » de « échec du LLM ». Aujourd'hui un JSON valide avec `steps` vide déclenche le repli sur IntentParser, qui peut mal interpréter la phrase (« fais un salto arrière » contient « arrière » -> le robot recule 1 s). Si le JSON est valide et que `steps` vaut explicitement [], retourne ([], {"source": "llm_unsupported", ...}) et fais rejeter la commande par handle_text_as_plan (status "rejected", reason "unsupported command", aucun mouvement, événement de trace dédié). Le repli IntentParser ne reste utilisé que pour timeout, erreur HTTP, JSON invalide ou clé `steps` absente.
9. Migration du modèle dans la config et la doc : remplace les références à Ministral 3B / « ministral.service » / ctx-size par Qwen2.5-1.5B-Instruct (GGUF Q4_K_M) dans scripts/install_llm.sh, l'unité systemd, README.md, PROJECT_CONTEXT.md et specs/03. Si le nom ou l'URL exacts du fichier GGUF te manquent, mets une variable (MODEL_FILE, MODEL_URL) avec un TODO et pose-moi UNE question. Garde --ctx-size 2048.

Tests (requests.post mocké) : plan complet du use case à partir de « cherche la balle jaune approche toi à un mètre de la balle jaune puis suis la pendant cinq minutes » (le LLM reçoit « … 100 centimètres … 300 secondes ») ; preprocess (nombres composés : quatre vingt dix, soixante et onze, deux cent cinquante, « un mètre » ; « un carré » inchangé) ; parser local qui comprend « cinquante centimètres » ; réponse entourée de backticks ; JSON invalide -> repli parseur ; étape malformée ignorée seule ; HTTP 400 -> nouvel appel sans response_format ; variables d'environnement prises en compte ; {"steps":[]} -> commande rejetée sans repli parseur et sans aucun mouvement (« fais un salto arrière »).
```

---

## Prompt 8b — Corrections après évaluation de Qwen2.5-1.5B

**Décision :** on garde le prompt système actuel (v1) avec sortie contrainte par schéma JSON. Le prompt v2 est abandonné (70 % contre 85 %).

Mesures (81 appels chacun, schéma JSON) :
- **v1 + schéma :** 69/81 corrects, aucune boucle de génération, latence médiane 1,9 s, max 5,5 s.
- **v2 + schéma :** 57/81, régressions sur les plans en plusieurs étapes (stops parasites) et boucle de 95 tokens.
- **Hors périmètre :** 0/9 refusés avec les deux prompts. Le modèle range « chante une chanson » en `spin_360`, « ouvre la porte du garage » en `move_forward 100`, « fais un salto arrière » en `avoid_obstacle` ou `move_backward`. Il faut une garde déterministe dans le code.
- **« arrête toi » :** renvoie `{"steps":[]}` : le stop doit passer sans LLM.
- **Latence :** le plan du use case prend 4,7–5,3 s, donc dépasse le timeout de 4 s.

```
Étape 8b/10 — Gardes déterministes autour du LLM (suppose le prompt 8 appliqué : text_normalizer.py, nouveau SYSTEM_PROMPT_PLAN, LLM_MODEL configurable). Fichiers : src/irobot/interfaces/voice_runtime.py, nouveau src/irobot/interfaces/plan_guards.py, tests/unit/test_plan_guards.py, tests/unit/test_voice_runtime.py. Référence : scripts/test/eval_prompt_plan.py (fonctions fold, is_pure_stop, grounding_check, constantes STOP_WORDS, INTENT_LEXICON, ALLOWED_PARAMS, PLAN_SCHEMA, build_formats). Ne modifie PAS SYSTEM_PROMPT_PLAN.

Principe : le LLM propose, le lexique dispose. Un petit LLM range parfois une phrase hors périmètre dans l'intent le plus proche ; aucune commande ne doit déclencher un mouvement si la phrase ne la justifie pas.

1. SÉCURITÉ — stop sans LLM : porte `is_pure_stop` (et STOP_WORDS) dans plan_guards.py. Dans handle_text_as_plan, AVANT tout appel au LLM et avant la normalisation de nombres, si is_pure_stop(texte) : exécute immédiatement un plan [stop], statut "accepted", source "local_stop". Ne le déclenche pas pour « avance puis arrête ». Le thread d'écoute de l'étape 7 (arrêt d'urgence pendant une mission) détecte déjà le stop avec IntentParser : fais-lui appeler is_pure_stop en premier, et garde IntentParser comme repli, sans changer le reste de son comportement.
2. Contrôle lexical : porte `grounding_check` (avec fold, INTENT_LEXICON, ALLOWED_PARAMS, NUMERIC_KEYS) SANS changer son comportement, et appelle-le sur les étapes du LLM après le parsing et avant la validation, en lui passant le texte PRÉTRAITÉ (celui envoyé au LLM, nombres en chiffres, minutes en secondes, mètres en centimètres) et non le texte brut. Règles : intent non justifié par un mot de la phrase -> plan rejeté ; `stop` non justifié -> étape supprimée ; paramètre que l'intent ne gère pas -> supprimé ; nombre absent de la phrase -> supprimé si la phrase ne contient aucun chiffre, plan rejeté sinon ; avance/recule sans distance ni durée -> duration 1 ; tourne sans angle ni durée -> angle 90. Un plan rejeté donne status "rejected", reason "unsupported command", AUCUN mouvement, AUCUN repli sur IntentParser, avec les notes dans la trace JSONL.
3. Hors périmètre explicite : un JSON valide avec `steps` == [] est aussi rejeté « unsupported command » sans repli parseur (le repli IntentParser ne sert que pour timeout, erreur HTTP, JSON invalide ou `steps` absent).
4. Timeout : LLM_READ_TIMEOUT_SECONDS passe à 8.0 par défaut (configurable par variable d'environnement) ; max_tokens du plan = 120.
5. Sortie contrainte par schéma : reprends PLAN_SCHEMA et build_formats. Essaie json_schema (strict), puis en cas de HTTP 400 {"type":"json_object","schema":PLAN_SCHEMA}, puis {"type":"json_object"}, puis rien ; mémorise le premier format accepté pour ne pas retenter les autres à chaque appel (sur mon serveur, json_schema est accepté du premier coup).
6. Parsing tolérant : étape sans "target" -> None ; sans "parameters" -> {}.
7. Garde-fous d'unité : après grounding_check, une `unit` éventuelle reste normalisée par l'étape 1 (le schéma n'émet pas `unit`, les distances sont en cm).

Tests (tests/unit/test_plan_guards.py + test_voice_runtime.py) : « stop », « arrête toi », « halte », « pause » -> plan [stop] sans appel LLM (requests.post non appelé) ; « avance puis arrête » et « arrête toi et recule » -> LLM appelé ; « chante une chanson » avec réponse LLM spin_360 -> rejeté sans mouvement ; « ouvre la porte du garage » avec move_forward 100 -> rejeté ; « fais un salto arrière » avec avoid_obstacle -> rejeté ; « avance » avec distance 1 -> duration 1 ; « avance de cinquante centimètres » avec distance 500 -> rejeté ; plan « avance de 20 puis recule de 10 » avec un stop parasite entre les deux -> stop supprimé ; « reviens au point de départ » avec return_to_start.duration=1 -> paramètre supprimé, plan accepté ; use case complet accepté ; steps vide -> rejeté sans repli ; chaîne de formats 400 ; timeout configurable.
```

---

## Prompt 8c — Diagnostic LLM et démarrage à froid

Constat (Mac, Qwen2.5-1.5B, serveur chaud) : le premier appel après démarrage a pris 35,6 s, puis 4 à 7 s pour le plan du use case ; ~11 tokens/s. Dans le runtime, la requête a dépassé 8 s et le repli sur le parseur local a pris le relais. La trace actuelle ne contient que le texte de l'erreur : impossible de savoir si la cause est le démarrage à froid, le préchauffage ou la contrainte de format.

```
Étape 8c/10 — Diagnostic et démarrage à froid du LLM. Fichiers : src/irobot/interfaces/voice_runtime.py, tests/unit/test_voice_runtime.py. Aucune autre modification de comportement.

1. Trace enrichie : dans l'événement plan_raw (et aussi quand l'appel échoue ou expire), ajoute : llm_latency_seconds (durée réelle de l'appel, même en cas d'erreur), llm_response_format (type du format finalement utilisé : json_schema | json_object_schema | json_object | none), llm_attempts (nombre de requêtes HTTP envoyées, repli de format inclus), llm_prompt_tokens, llm_completion_tokens (champ usage de la réponse), llm_timings (copie du champ `timings` renvoyé par llama-server s'il existe : prompt_per_second, predicted_per_second, etc.), error_type (nom de l'exception).
2. Format de sortie réglable sans modifier le code : variable d'environnement LLM_RESPONSE_FORMAT = schema (défaut) | json_object | none. "schema" garde la chaîne de repli de l'étape 8b ; "json_object" n'envoie que {"type":"json_object"} ; "none" n'envoie aucun response_format. Ce réglage sert à comparer la vitesse sur le Pi.
3. Démarrage à froid : en mode une seule commande (--once ou --text), attends la fin du préchauffage avant d'envoyer la vraie requête (timeout LLM_WARMUP_WAIT_SECONDS, défaut 60). Si le préchauffage échoue ou expire, continue quand même (repli parseur en cas de besoin) et note-le dans la trace (warmup_status : done | failed | timeout | skipped). En mode écoute continue, le préchauffage reste en arrière-plan sans bloquer.
4. Message console lisible quand le repli se déclenche : « LLM trop lent (> Xs), repli sur le parseur local » (ou le motif réel : serveur injoignable, JSON invalide, etc.).
5. Timeout : passe le défaut de LLM_READ_TIMEOUT_SECONDS de 8.0 à 10.0 (constante, documentation, tests et PROJECT_CONTEXT.md). Mesures : le plan du use case prend 4,3 à 7,7 s serveur chaud, et le dépassement à 8 s a déjà déclenché un repli inutile.

Tests (requests.post mocké) : le défaut du timeout de lecture vaut 10.0 ; la trace contient llm_latency_seconds, llm_attempts et error_type en cas de timeout ; LLM_RESPONSE_FORMAT=none n'envoie pas response_format ; json_object envoie le format simple ; en mode --text la vraie requête n'est envoyée qu'après le préchauffage ; préchauffage en échec -> la commande est quand même traitée.
```

Commit : `feat(llm): trace de latence, format de sortie réglable, attente du préchauffage`

---

## Prompt 9 — Test de scénario complet

```
Étape 9/10 — Scénario bout en bout (sans matériel). Fichiers : tests/unit/test_voice_runtime.py (ou nouveau tests/unit/test_scenario_yellow_ball.py), tests/unit/fake_robot.py.

Crée un test qui exécute VoiceRuntime(use_llm=False, threaded=False) avec FakeRobot et une perception simulée qui rejoue ce scénario avec une horloge simulée (aucun sleep réel) :
1. Balle absente pendant 4 s puis visible à droite à 220 cm.
2. La balle devient centrée ; l'approche réduit la distance jusqu'à ≈ 100 cm (stand_off atteint).
3. Pendant 300 s simulées, la balle se déplace (s'éloigne, se rapproche, sort du champ 2 s puis revient) ; le robot suit et garde ≈ 100 ± 15 cm.
4. Fin de mission à 300 s : robot arrêté, statut global "accepted".
Entrée : « cherche la balle jaune, approche toi à 1m de la balle jaune puis suit la pendant 5 min ».

Ajoute aussi :
- un scénario de balle jamais trouvée (search_timeout) : statut "incomplete", robot arrêté, pas de suivi lancé ;
- un scénario avec arrêt d'urgence à t=60 s : robot arrêté, mission interrompue ;
- un scénario avec obstacle à t=100 s : robot arrêté.
Vérifie dans chaque cas que `robot.stop()` a bien été appelé en dernier et que la trace JSONL contient les événements attendus.
```

---

## Prompt 10 — Documentation, essai sur Pi, commit

```
Étape 10/10 — Finalisation.
1. Mets à jour PROJECT_CONTEXT.md (section « Réalisé et validé » + « Restant ») : nouvelles intents (follow_object), paramètres (stand_off_cm, duration_s, search_timeout_s), estimation de distance, arrêt d'urgence, nouvelles clés du TOML. Mets à jour README.md (commandes `calibrate-distance`, exemple de commande vocale).
2. Mets à jour specs/ si un fichier décrit la liste des intents/skills.
3. Ajoute scripts/test/run_runtime_standard_scenarios_mac.sh un scénario « balle jaune » (mock de perception).
4. Lance `pytest` et résume les échecs éventuels.
5. /cp
```

---

## Prompt 11 — Nettoyage : installation LLM, scripts Mac, documentation (optionnel, après l'étape 10)

À donner dans un nouveau chat, une fois le use case validé sur le Pi. Ne change aucun comportement du robot : uniquement des scripts et de la documentation.

```
Étape 11 — Nettoyage et cohérence après la migration vers Qwen2.5-1.5B. Fichiers : scripts/install_llm.sh, scripts/install_llm_mac_portable.sh, scripts/test/run_llm_runtime_mac.sh, tests d'intégration LLM (tests/integration/), README.md, PROJECT_CONTEXT.md, REFERENCE_IROBOT.md, specs/03_llm_model_strategy.md. Aucun changement de code dans src/.

1. scripts/install_llm.sh :
   - PROJECT_DIR pointe aujourd'hui vers scripts/install : corrige-le pour qu'il désigne la racine du dépôt (parent de scripts/), de façon robuste quel que soit le répertoire d'où le script est lancé, de sorte que `uv sync` s'exécute au bon endroit.
   - Le message final cite encore `voice-assistant` : remplace par `uv run voice-runtime` et ajoute la commande de test `python3 scripts/test/eval_prompt_plan.py --schema`.
   - Rends configurables par variables d'environnement, avec ces défauts : LLM_CTX_SIZE=2048, LLM_THREADS=$(nproc), LLM_PARALLEL=1, et passe-les à llama-server (--ctx-size, --threads, --parallel). Ne change pas le nom de l'unité systemd (ministral.service) : ajoute plutôt un commentaire expliquant que ce nom est conservé pour compatibilité.
2. Scripts Mac (install_llm_mac_portable.sh, run_llm_runtime_mac.sh) : remplace Ministral-3-3B par Qwen2.5-1.5B-Instruct (GGUF Q4_K_M) avec le même nom de fichier/URL que scripts/install_llm.sh (variables MODEL_FILE / MODEL_URL partagées si possible), aligne --ctx-size sur LLM_CTX_SIZE (défaut 2048 au lieu de 4096) et ajoute --parallel 1. Le but : tester sur Mac le même modèle que sur le Pi.
3. Test(s) d'intégration LLM : retire toute valeur codée en dur liée à Ministral ou à ctx-size 4096 ; lis le modèle et l'URL depuis les variables d'environnement (LLM_MODEL, LLM_URL) avec les défauts du runtime.
4. Documentation : cherche avec grep -ri "ministral" (hors historique git) et remplace ou reformule chaque occurrence restante dans README.md, PROJECT_CONTEXT.md, REFERENCE_IROBOT.md (section « Commandes utiles »), specs/03. Garde la mention du nom d'unité ministral.service avec son explication. Dans README.md, remplace la commande de démarrage recommandée `voice-assistant` par `voice-runtime` (garde voice-assistant uniquement s'il est cité comme legacy).
5. Vérifie à la fin : `grep -ri "ministral\|ctx-size 4096\|voice-assistant" .` ne doit plus renvoyer que les occurrences volontaires (nom d'unité systemd, mention legacy) ; liste-les-moi. Lance `pytest` et `bash -n` sur chaque script modifié (vérification de syntaxe).

Ne lance AUCUN téléchargement de modèle ni installation. Pose-moi UNE question seulement si le nom ou l'URL du fichier GGUF est introuvable dans le dépôt.
```

Commit : `chore(llm): alignement des scripts et de la doc sur Qwen2.5-1.5B`

---

## Protocole d'essai réel sur le Pi (à faire toi-même, pas Copilot)

1. **Roues en l'air** (robot sur cale) : vérifier sens des moteurs, arrêts, « stop » vocal.
2. **Calibration distance** : `uv run calibrate-distance --known-distance-cm 100` avec la balle à 1 m → reporter `focal_px` dans le TOML ; vérifier à 50 / 150 / 200 cm.
3. **Calibration mouvement** : ajuster `cm_per_second` et `deg_per_second` (avance 100 cm, rotation 360°).
4. **Approche seule** (« approche-toi de la balle jaune à 1 m ») sur sol dégagé, en marche lente.
5. **Suivi court** (30 s) avant le suivi de 5 min ; garde une main près du robot / de l'alimentation.
6. Mesure le temps de réponse du LLM sur le Pi (traces JSONL) : si le repli local survient trop souvent, ajuste `LLM_READ_TIMEOUT_SECONDS` ou raccourcis encore le prompt (étape 8).
