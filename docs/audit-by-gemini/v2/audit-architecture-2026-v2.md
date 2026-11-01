# Rapport d'Audit d'Architecture et de Qualité de Code (V2) — mathleros-conf_raspberrypi

**Date :** 24 octobre 2026  
**Projet :** `irobot` / Banc d'essai robotique autonome Raspberry Pi 5  
**Version évaluée :** Post-application des 5 chantiers prioritaires (Packaging, Sécurité active, Suivi en boucle fermée, Factorisation DRY & Blackboard, Watchdog LLM/Audio).

---

## Synthèse d'avancement des 5 chantiers initiaux

| Chantier initial | Statut | Constat dans le code audité |
|---|:---:|---|
| **P1 : Restauration des entrypoints & packaging** | **Validé** | `pyproject.toml` réaligné sur `irobot.hardware.*`. `voice_assistant:main` délègue proprement à `voice_runtime_main`. |
| **P2 : Mouvements non bloquants & Sécurité active** | **Validé** | `RobotController._run_motion_for()` cadence les mouvements à 20 ms et vérifie les obstacles et arrêts d'urgence en continu. |
| **P3 : Boucle fermée de suivi (Closed-Loop)** | **Partiel** | Boucle de suivi `while` implémentée dans `FollowTargetSkill` (asservissement angulaire, seuils de perte), mais dépend encore d'un mock/simulation (pas de driver caméra live connecté). |
| **P4 : Factorisation DRY & BlackboardState** | **Validé** | Création de `BaseMotionPrimitiveSkill` (4 primitives factorisées), de `BlackboardState` (typage de l'état partagé) et de `audio_utils.py` (mutualisation ALSA/Bluetooth). |
| **P5 : Watchdog LLM & Processus audio** | **Validé** | Timeout HTTP LLM strict `(1.0s connect, 4.0s read)`. Gestionnaire de contexte `_arecord_stream` avec `terminate()` et `kill()` garanti. |

---

## 1. Architecture & Structure

### Points forts
* **Factorisation réussie des primitives :** L'introduction de `BaseMotionPrimitiveSkill` (`src/irobot/domain/skills/primitives/base_motion_primitive.py`) a considérablement assaini la couche domaine. Les classes `MoveForwardSkill`, `MoveBackwardSkill`, `TurnLeftSkill` et `TurnRightSkill` ne sont plus que des déclarations déclaratives et configurables.
* **Typage et rétrocompatibilité via `BlackboardState` :** La mise en place de `BlackboardState` (`src/irobot/domain/skills/blackboard_state.py`) formalise un contrat de données clair (`KNOWN_FIELDS`) tout en préservant le contrat `MutableMapping[str, Any]` pour garantir une rétrocompatibilité parfaite avec l'existant.
* **Mutualisation audio propre :** La création de `audio_utils.py` résout l'éparpillement des appels système de détection audio ALSA et Bluetooth.

### Faiblesses et incohérences résiduelles
* **Code mort persistant dans `voice_assistant.py` :**
  Même si le point d'entrée `main()` redirige désormais vers `voice_runtime_main()`, le fichier conserve l'intégralité de la classe `VoiceCarController` (110 lignes de logique concurrente) et de la fonction `legacy_main()`. Cela entretient une fausse piste de lecture et doit être supprimé.
* **Rupture de chaîne sur la perception caméra réelle :**
  Il existe `SimulatedObjectPerception` (`hardware/camera/simulated_perception.py`) pour les tests et le script autonome `color_detector.py`. En revanche, **aucune classe n'implémente `ObjectPerceptionPipeline` pour la caméra physique**. Lors de l'instanciation de `VoiceRuntime` dans `main()`, `perception=None`. Le robot retombe donc systématiquement dans le mode dégradé "one-pulse" sans boucle fermée.

---

## 2. Adéquation au Besoin Fonctionnel

### Ce qui est désormais résolu
* **Interruption immédiate sur obstacle :** Grâce à la boucle de cadencement à 20 ms dans `_run_motion_for()`, une trajectoire de plusieurs secondes est stoppée net en moins de 20 ms en cas de détection d'obstacle ou d'arrêt d'urgence.
* **Garde-fous sur perte visuelle :** Dans `FollowTargetSkill`, les paramètres `max_target_loss_s` (1.0 s) et `tracking_timeout_s` (8.0 s) protègent le robot d'un emballement aveugle lorsque la cible sort du champ visuel.
* **Reprise de contrôle vocale rapide :** Avec les timeouts HTTP stricts (1s connexion / 4s lecture), le fallback local `IntentParser` prend le relais en moins de 5 secondes en cas d'indisponibilité ou de saturation du modèle local `llama-server`.

### Écarts subsistants avec le fonctionnement physique
* **Dynamique de déplacement "Staccato" (Micro-à-coups) :**
  Dans `FollowTargetSkill._pulse_motion()`, le robot effectue des micro-déplacements de `0.08s` (rotation) et `0.12s` (avance) suivis systématiquement d'un arrêt complet (`self._stop_robot()`).
  Sur un châssis 2WD avec moteurs à courant continu et réducteurs, ces démarrages/arrêts répétés provoquent des à-coups mécaniques, des chutes de tension batterie et du patinage, dégradant la fluidité du suivi.
* **Point d'entrée CLI non câblé sur le matériel :**
  Dans `src/irobot/interfaces/voice_runtime.py:main()`, `runtime = VoiceRuntime(...)` est instancié avec `robot=None` et `perception=None`. Lancer `uv run voice-runtime` sur le Raspberry Pi n'actionne pas la voiture sans ajout d'une factory d'injection matérielle.

---

## 3. Qualité & Maintenabilité du Code

* **Sortie brutale `os._exit(0)` résiduelle :**
  Dans `smart_car.py` (l. 288) et `hc_sr04.py` (l. 138), `os._exit(0)` persiste dans les blocs `finally`. Bien qu'utilisé pour contourner les blocages de threads internes de `gpiozero`, cela coupe net l'interpréteur Python sans laisser les destructeurs et context managers flusher les flux ouverts.
* **Attente active non-temps réel dans `hc_sr04.py` :**
  Dans `_wait_for_level` (`hc_sr04.py`), la mesure s'appuie sur `time.sleep(0.00001)`. Sous Linux standard non-RT sur Pi 5, la préemption du thread par l'ordonnanceur peut introduire une dérive de 1 à 5 ms, faussant la distance mesurée de 15 à 80 cm.
* **Comportement de `BlackboardState.__delitem__` :**
  Dans `blackboard_state.py` (l. 68-71), supprimer une clé connue la réinitialise à `None` sans avertissement, au lieu de restaurer sa valeur par défaut ou de lever une exception si le champ est obligatoire.

---

## 4. Sécurité & Performances

* **Effet de bord bloquant du Fail-Safe d'obstacle :**
  Dans `SmartCar2WD.check_obstacle()` (`smart_car.py`) :
  ```python
  def check_obstacle(self) -> bool:
      if self.distance_sensor is None:
          return True  # FAIL-SAFE ABSOLU
  ```
  Le principe du Fail-Safe est rigoureux, mais si la voiture est testée sans capteur HC-SR04 connecté (ou lors d'un test moteur simple sur banc), `check_obstacle()` renvoie `True` en continu.
  *Conséquence :* `_run_motion_for()` coupe instantanément les moteurs et **la voiture refuse tout déplacement**, sans message d'erreur explicite sur l'absence du capteur.
* **Concurrence & Acquisition vidéo :**
  Dans une boucle de suivi visuel cadencée à 50 Hz (`CONTROL_LOOP_PERIOD_S = 0.02`), un appel synchrone à `picam2.capture_array()` bloque le thread de 30 à 60 ms par image. L'acquisition d'images doit obligatoirement être déportée dans un thread d'arrière-plan avec un tampon à une seule image (single-frame buffer) pour éviter de saturer la boucle de contrôle.

---

## 5. Plan d'Action Prioritaire (Chantiers de la version 2)

| Priorité | Chantier | Action technique concrète | Bénéfice & Impact |
|---|---|---|---|
| **P1** | **Pipeline de perception caméra réelle (Threadé)** | Développer `CameraLivePerceptionPipeline` (implémentant `ObjectPerceptionPipeline`) encapsulant `Picamera2` et `ColorDetector` dans un thread de capture continu sans blocage du thread principal. | **Critique :** Permet à `FollowTargetSkill` d'exécuter sa boucle fermée sur le robot réel au lieu du mode dégradé. |
| **P2** | **Lissage du suivi visuel (Asservissement proportionnel continu)** | Remplacer les micro-impulsions hachées (`_pulse_motion`) par une régulation continue des vitesses PWM gauche/droite (`set_speed` différentiel) sans couper les moteurs à chaque itération. | **Mécanique & Contrôle :** Supprime les à-coups violents, protège l'alimentation et stabilise la trajectoire de suivi. |
| **P3** | **Gestion configurable de l'absence de capteur d'obstacle** | Dans `SmartCar2WD`, ajouter un drapeau `require_obstacle_sensor: bool = False` pour distinguer une défaillance de capteur (qui doit déclencher le Fail-Safe) d'un mode de test délibéré sans capteur. | **Exploitation :** Empêche le blocage total du robot lors des tests mécaniques ou des ateliers sans capteur ultrason. |
| **P4** | **Purge de la dette technique legacy** | Supprimer `VoiceCarController` et `legacy_main` de `voice_assistant.py` ; isoler `os._exit(0)` derrière une option CLI stricte (`--force-exit`) pour préserver les tests et les appels modulaires. | **Qualité & Propreté :** Supprime plus de 150 lignes de code mort et fiabilise le cycle de vie du processus Python. |
| **P5** | **Factory d'injection matérielle pour la CLI** | Dans `voice_runtime.py:main`, introduire une fonction `build_production_runtime()` instanciant automatiquement les vrais drivers (`SmartCar2WD`, `CameraLivePerceptionPipeline`, etc.) si exécuté sur Raspberry Pi. | **Usabilité :** Rend la commande `uv run voice-runtime` immédiatement opérationnelle sur le robot physique. |
