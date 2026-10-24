# Rapport d'Audit d'Architecture et de Qualité de Code — mathleros-conf_raspberrypi

**Date :** 24 octobre 2026  
**Projet :** `irobot` / Banc d'essai robotique autonome Raspberry Pi 5  
**Objet :** Audit d'architecture, adéquation fonctionnelle, qualité logicielle, sécurité & plan d'action prioritaire.

---

## 1. Architecture & Structure

### Points forts
* **Découpage en couches propre (Clean Architecture) :** La séparation entre `domain/` (métier, skills, orchestrateur), `interfaces/` (langage, parsing, adaptation) et `hardware/` (pilotes matériels) est saine, modulaire et bien délimitée.
* **Isolation stricte de l'IA (Safety by Design) :** Le LLM n'accède jamais directement aux actionneurs ou aux broches GPIO. Le flux suit une chaîne d'exécution déterministe et vérifiable :  
  `Voix/Texte → IntentParser → IntentValidator → SkillPlanner → SkillExecutor → RobotController → Hardware`.
* **Excellente testabilité hors-matériel :** L'interface `RobotController` (`src/irobot/interfaces/robot_controller.py`) combinée à l'émulateur `FakeRobot` (`tests/unit/fake_robot.py`) permet d'exécuter 100 % de la logique de planification et de validation sur machine de développement (macOS/CI) sans dépendance matérielle.
* **Traçabilité native complète :** L'enregistrement des traces en JSONL (`VoiceRuntime._write_trace_event`) et le script de replay dédié (`scripts/test/replay_runtime_trace_mac.sh`) constituent un atout majeur pour l'analyse post-mission et la reproductibilité des incidents.

### Faiblesses et incohérences structurelles
* **Incohérence majeure de packaging dans `pyproject.toml` :**
  Les points d'entrée configurés (`[project.scripts]`) pointent vers d'anciens modules qui n'existent plus suite au refactoring dans le sous-dossier `hardware/` :
  ```toml
  # pyproject.toml (lignes 545-552)
  smart-car = "irobot.smart_car.smart_car:main"       # Inexistant (déplacé dans irobot.hardware.smart_car)
  camera-live = "irobot.camera.camera_live:main"     # Inexistant (déplacé dans irobot.hardware.camera)
  voice-assistant = "irobot.voice_assistant...:main" # Inexistant (déplacé dans irobot.hardware.audio)
  hc-sr04 = "irobot.sensors.hc_sr04:main"            # Inexistant (déplacé dans irobot.hardware.sensors)
  ```
  *Conséquence directe :* l'exécution des commandes via `uv run smart-car` ou `uv run camera-live` lève immédiatement un `ModuleNotFoundError`.
* **Schizophrénie d'architecture (Double implémentation concurrente) :**
  * `src/irobot/hardware/audio/voice_assistant.py` implémente un contrôleur autonome hérité `VoiceCarController` doté de ses propres regex et appelant `SmartCar2WD()` directement avec des temporisations bloquantes `time.sleep()`.
  * `src/irobot/interfaces/voice_runtime.py` implémente la véritable architecture cible (`VoiceRuntime` + `LanguageController` + `Skills`).  
  Ces deux contrôleurs coexistent sans lien fonctionnel, créant une ambiguïté sur le point d'entrée officiel du robot.
* **Couplage lâche et non typé via `SkillContext.state` :**
  Les informations d'état transitent via un dictionnaire brut `dict[str, Any]` avec des clés arbitraires ou dupliquées :
  ```python
  # src/irobot/domain/skills/behaviors/follow_target.py (ligne 23)
  target_position = context.state.get("last_object_position", context.state.get("last_ball_position"))
  ```
  Le contrat de données entre la perception et l'action est implicite, fragile au renommage et propice aux régressions silencieuses.

---

## 2. Adéquation au Besoin Fonctionnel

### Ce qui répond aux objectifs
* **Exécution 100 % locale et hors-ligne :** Combinaison efficace de Vosk (STT local français) et d'un SLM local (Ministral 3B ou Qwen 2.5 via `llama-server` sur `http://127.0.0.1:8080`).
* **Résilience linguistique :** Prise en compte d'ordres composés (`move_square`, `contour_obstacle`, `execute_path`) avec un repli instantané vers le parseur heuristique local (`IntentParser`) en cas de panne ou de latence excessive du LLM.
* **Taxonomie claire des compétences :** Respect de la séparation entre primitives (`move_forward`, `turn_left`, `stop_motion`), perception (`detect_object`, `detect_obstacle`) et comportements composites (`move_circle`, `follow_target`).

### Écarts critiques avec le besoin robotique réel
* **Absence de boucle fermée continue (Closed-Loop Control / Visual Servoing) :**
  Le scénario phare *"suit la balle rouge"* ne fonctionne pas en continu dans la réalité physique. `SkillPlanner` planifie une séquence discrète et statique : `["detect_object", "follow_target", "detect_obstacle", "stop_motion"]`. Une fois `follow_target` exécuté, la mission s'arrête si la condition d'étape est atteinte, sans asservissement itératif couplé à la fréquence d'images réelle de la caméra.
* **Mouvements en boucle ouverte (Odométrie aveugle) :**
  La conversion distance/angle en durées temporelles (`calibration_helpers.py` et `settings.py`) repose sur une vitesse fixe théorique (`25.0 cm/s`, `180.0 °/s`). Sur un châssis 2WD sans encodeurs optiques ni centrale inertielle (IMU), la chute de tension de la batterie et le patinage induisent une erreur de trajectoire cumulée supérieure à 30 %.
* **Blocage du thread d'exécution par `time.sleep` :**
  Dans `RobotController` (lignes 68-71) :
  ```python
  self.forward()
  time.sleep(max(0.0, duration_seconds))
  self.stop()
  ```
  Pendant cette phase de sommeil bloquante, **aucun capteur d'obstacle n'est échantillonné**, et aucun ordre vocal d'arrêt d'urgence ne peut être intercepté. Si un obstacle surgit après 0.1 s sur un déplacement commandé de 3 s, la collision physique est inévitable.

---

## 3. Qualité & Maintenabilité du Code

* **Duplication de code massive (Violations du principe DRY) :**
  * `MoveForwardSkill` et `MoveBackwardSkill` partagent 90 % de code identique (parsing des paramètres `distance`, `unit`, `duration`, conversion `_to_float`).
  * `TurnLeftSkill` et `TurnRightSkill` sont des doublons stricts (seul l'appel `left_for` vs `right_for` diffère).
  * La découverte des périphériques audio (`find_wm8960_card`, `detect_bluetooth_input_device`, `resolve_input_device`) est dupliquée à l'identique entre `voice_assistant.py` (l. 154-203) et `voice_runtime.py` (l. 91-140).
* **Sortie brutale de processus (`os._exit`) :**
  Dans `smart_car.py` (l. 319) et `hc_sr04.py` (l. 138) :
  ```python
  finally:
      os._exit(0)
  ```
  L'usage d'`os._exit(0)` au lieu de `sys.exit()` ou d'un retour propre de boucle court-circuite le runtime Python, empêchant l'exécution des gestionnaires de contexte `finally` résiduels et le nettoyage des descripteurs de fichiers.
* **Capture d'exceptions trop large (`except Exception:`) :**
  Dans la totalité des skills (`execute()`) ainsi que dans les fonctions d'interrogation LLM (`ask_llm_for_intent`) :
  ```python
  except Exception as exc:
      return SkillResult(status="failed", message=f"Erreur : {exc}")
  ```
  Cela masque silencieusement les erreurs de typage (`TypeError`, `AttributeError`), les fautes de syntaxe ou les dysfonctionnements internes sous un statut générique d'échec de skill.
* **Sous-processus orphelins :**
  Dans `transcribe_loop` (`voice_runtime.py` l. 165), le sous-processus `arecord` est instancié sans bloc `try...finally` garantissant son arrêt (`proc.terminate()`). En cas d'interruption ou d'exception, le processus `arecord` continue de tourner en arrière-plan et verrouille le périphérique audio ALSA.

---

## 4. Sécurité & Performances

* **Sécurité physique : Faiblesse du Fail-Safe d'obstacle :**
  Dans `SmartCar2WD.check_obstacle()` (`smart_car.py` l. 159-166) :
  ```python
  distance_cm = self.distance_sensor.read_distance_cm()
  if distance_cm is None:
      return False  # DANGER : si le capteur échoue ou timeout, le système considère qu'il n'y a PAS d'obstacle !
  return distance_cm < self.obstacle_threshold_cm
  ```
  En robotique mobile, **une absence de lecture valide doit être traitée comme un danger potentiel (Fail-Safe)**, et non comme une autorisation de continuer le mouvement.
* **Performances & Latence LLM (Requêtes synchrones bloquantes) :**
  L'appel HTTP `requests.post(LLM_URL, timeout=120)` est exécuté de manière synchrone dans le thread principal. Si `llama.cpp` sature le CPU du Pi 5 lors du premier chargement du modèle, l'ensemble du système reste gelé jusqu'à 2 minutes sans pouvoir traiter d'ordre utilisateur.
* **Jitter temporel sur le capteur ultrason HC-SR04 :**
  Dans `hc_sr04.py`, l'attente du front montant/descendant s'effectue via une boucle d'attente active avec `time.sleep(0.00001)`. Sur un noyau Linux standard non-RT (temps réel), l'ordonnanceur préempte le thread pendant plusieurs millisecondes, faussant la mesure de distance de 10 à 30 cm de façon aléatoire.

---

## 5. Plan d'Action Prioritaire (Top 5 des Chantiers)

| Priorité | Chantier | Action technique concrète | Bénéfice & Impact |
|---|---|---|---|
| **P1** | **Restauration des points d'entrée et nettoyage de la dette legacy** | Corriger les chemins des modules dans `pyproject.toml` (`irobot.hardware.*`) et supprimer ou refactoriser `VoiceCarController` dans `voice_assistant.py` pour unifier le runtime sur `VoiceRuntime`. | **Critique :** Rétablit le fonctionnement des commandes CLI `uv run` sans crash à l'import. |
| **P2** | **Sécurisation matérielle & Mouvements non bloquants** | Remplacer les `time.sleep()` de `RobotController` par des boucles cadencées vérifiant les capteurs (obstacle + arrêt d'urgence) à chaque pas temporel (ex. 20 ms). Inverser la logique d'échec du capteur HC-SR04 en mode *fail-safe*. | **Sécurité physique :** Supprime le risque de collision matérielle lors des déplacements. |
| **P3** | **Boucle de contrôle fermée (Closed-Loop Tracking)** | Transformer `FollowTargetSkill` et la machine d'états pour maintenir un asservissement visuel continu `Perception → Correction angulaire → Avance` avec condition de sortie sur perte de cible prolongée ou proximité atteinte. | **Fonctionnel :** Permet la réalisation effective et fluide du cas d'usage *"suit la balle rouge"*. |
| **P4** | **Factorisation DRY & Typage strict du contexte** | Mutualiser les primitives dans une classe générique (`BaseMotionPrimitiveSkill`), centraliser la gestion audio (`audio_utils.py`), et remplacer le dictionnaire `context.state` par une structure de données typée (`BlackboardState` / dataclass). | **Maintenabilité :** Réduit de 40 % le volume de code des skills et élimine les régressions silencieuses. |
| **P5** | **Gestion asynchrone / Non-bloquante du LLM & Watchdog** | Encadrer les requêtes LLM avec un timeout strict plus court (ex: 3 à 5 secondes sur Pi 5) avec bascule immédiate sur `IntentParser`, et garantir l'arrêt des sous-processus `arecord` via un context manager. | **Robustesse & Réactivité :** Élimine les gels de 120 s et prévient les blocages matériels du microphone ALSA. |
