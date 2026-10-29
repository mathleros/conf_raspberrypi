# 1. Inventaire des skills existants et des écarts

## Contrat runtime livré (2026-10-29)

Les sections suivantes conservent le cadrage historique ; le contrat implémenté pour la mission balle est :

| Intent validé | Skills du planner | Paramètres |
|---|---|---|
| `search_and_approach_object` | `detect_object`, `follow_target`, `detect_obstacle`, `stop_motion` | cible `red`/`yellow`, `stand_off_cm`, `search_timeout_s` |
| `follow_object` | `follow_object` | cible `red`/`yellow`, `stand_off_cm`, `duration_s`, `search_timeout_s` |
| `follow_red_ball` (compatibilité) | `detect_object`, `follow_target`, `detect_obstacle`, `stop_motion` | cible `red_ball` ou absente |

`follow_target` assure recherche, alignement et approche jusqu'à la distance de consigne ; `follow_object` maintient ensuite cette distance par impulsions avant/arrière et rotations, pendant la durée demandée. La perte de cible provoque un arrêt puis un balayage ; l'épuisement du budget de recherche échoue avec `target_lost=True`. Urgence/obstacle arrête la skill et le runtime classe la mission `aborted`, sans retry ni poursuite du plan.

Bornes du TOML livré : `stand_off_cm` 30–300 cm (`min_stand_off_cm`/`max_stand_off_cm`), `duration_s` 1–600 s (`max_follow_duration_sec`), `search_timeout_s` 1–120 s (défaut `search_timeout_seconds=25`). La durée de suivi inclut la recherche ; tolérance de suivi par défaut 15 cm. `timeout_margin_seconds=10` intervient dans le budget d'étape avec durée explicite.

La perception live estime la distance par diamètre apparent (`focal_px * ball_diameter_cm / diameter_px`) avec lissage ; `[camera]` expose `ball_diameter_cm`, `focal_px` et `ultrasonic_fusion` (désactivée par défaut). Calibration sur Pi : `uv run calibrate-distance --color yellow --known-distance-cm 100`. Aucun capteur arrière : le recul du suivi exige une zone dégagée.

Le LLM ne choisit pas les commandes moteur : `Intent` -> validation/bornage -> planner/skills -> `RobotController`. Les boucles sont testées sans matériel avec `FakeRobot`, `time_fn` et `sleep_fn`.

## 1.1 Méthode d'inventaire

L'inventaire a été réalisé à partir des modules du dépôt :
- `src/irobot/smart_car/smart_car.py`
- `src/irobot/camera/color_detector.py`
- `src/irobot/camera/camera_live.py`
- `src/irobot/sensors/hc_sr04.py`
- `src/irobot/voice_assistant/voice_assistant.py`
- `scripts/install_llm.sh`
- `README.md`, `PROJECT_CONTEXT.md`

## 1.2 Skills déjà disponibles

### A. Skills de mouvement / actionnement

1. `move_forward`
- Implémentation : `SmartCar2WD.forward()`
- Fonction : avance en ligne droite
- État : disponible et testable
- Paramètres : vitesse, durée facultative

2. `move_backward`
- Implémentation : `SmartCar2WD.backward()`
- Fonction : recule
- État : disponible

3. `turn_left`
- Implémentation : `SmartCar2WD.left()`
- Fonction : rotation gauche
- État : disponible

4. `turn_right`
- Implémentation : `SmartCar2WD.right()`
- Fonction : rotation droite
- État : disponible

5. `stop_motion`
- Implémentation : `SmartCar2WD.stop()`
- Fonction : arrêt moteur
- État : disponible

6. `set_speed`
- Implémentation : `SmartCar2WD.set_speed()`
- Fonction : règle la vitesse globale du robot
- État : disponible

7. `check_obstacle`
- Implémentation : `SmartCar2WD.check_obstacle()`
- Fonction : détecte si un objet est trop proche du capteur de distance
- État : disponible, mais utilisé comme simple garde-fou et non comme orchestrateur global

### B. Skills de perception / capteurs

8. `capture_camera_live`
- Implémentation : `camera_live.py`
- Fonction : ouvre le flux de la caméra et affiche le flux
- État : disponible

9. `detect_red_or_yellow_object`
- Implémentation : `color_detector.py`
- Fonction : détecte suiveur de couleur rouge / jaune, classe en balle ou objet
- État : disponible

10. `detect_target_position_in_frame`
- Implémentation : `get_object_position()`
- Fonction : retourne une zone approximative (centre, haut, bas, gauche, droite etc.)
- État : disponible mais non encore structuré comme skill réutilisable

11. `read_distance_hcsr04`
- Implémentation : `HC_SR04.read_distance_cm()`
- Fonction : mesure la distance du premier objet détecté devant le capteur
- État : disponible

12. `distance_map_single_sensor`
- Implémentation : par le service de distance, non encore intégré dans un système de navigation
- Fonction : représente la distance mesurée en cm
- État : partiellement disponible

### C. Skills de perception audio / voix

13. `capture_microphone`
- Implémentation : `transcribe_loop()`
- Fonction : lit le flux audio brut du microphone
- État : disponible

14. `speech_to_text_vosk`
- Implémentation : `vosk.Model` + `KaldiRecognizer`
- Fonction : transcrit la voix en texte
- État : disponible

15. `voice_command_to_text`
- Implémentation : `transcribe_loop()` + parsing d'entrées
- Fonction : convertit une phrase parlée en texte exploitable
- État : disponible

16. `understand_voice_command`
- Implémentation : `VoiceCarController.handle_text()`
- Fonction : interprète des commandes simples pour le robot
- État : disponible pour des commandes rudimentaires (avance, recule, gauche, droite, stop)

17. `llm_chat_local`
- Implémentation : `ask_llm()` via `llama-server`
- Fonction : interroge le LLM local et renvoie une réponse textuelle
- État : disponible

### D. Skills de coordination / raisonnement

18. `parse_instruction_as_natural_language`
- Implémentation : LLM + prompt système
- Fonction : transforme une consigne en intention
- État : partiellement présent, non structuré de façon robuste

19. `voice_control_car_simple`
- Implémentation : `voice-assistant --car`
- Fonction : pilote le robot selon des commandes vocales simples
- État : disponible

## 1.3 Corrections de conception sur la hiérarchie des skills

Après validation du besoin et du principe d'orchestration, la taxonomie des skills doit être clarifiée :

### A. Skills primitives (atomiques)

Ces skills représentent les actions directement exécutables par le robot sur ses actionneurs.

- `move_forward`
- `move_backward`
- `turn_left`
- `turn_right`
- `stop_motion`

Elles sont simples, courtes et déterministes, et servent de briques de base pour les tâches complexes.

### B. Skills de perception et de mesure

- `detect_red_ball`
- `detect_obstacle`
- `read_distance`
- `localize_target` (à ajouter si nécessaire)

### C. Behaviors composites (tâches complexes)

Ce sont des séquences de skills primitives couplées à de la perception, par exemple :

- `follow_target`
- `follow_object` (suivi à distance constante pendant `duration_s`)
- `align_to_target`
- `approach_target`
- `avoid_obstacle`
- `move_circle`

Le comportement `move_circle` n'est pas une primitive. Il doit être composé par l'orchestrateur à partir de `turn_left` + `move_forward` + `stop_motion` avec durée et vitesse paramétrées.

### Règle de conception

Le LLM doit produire un comportement ou une intention de haut niveau, jamais un ordre moteur brute. L'orchestrateur transforme ensuite cette intention en séquence de skills primitives.

### Impact sur l'architecture

Cette clarification a plusieurs effets positifs :
- cohérence entre la logique des skills et la réalité du robot ;
- meilleur testabilité unitaire ;
- meilleure lisibilité du code ;
- plus de robustesse sur les tâches composées ;
- meilleure séparation entre prise de décision et exécution robotique.

## 1.4 Synthèse du niveau de maturité

Les compétences unitaires sont présentes et la plupart sont fonctionnelles. Le manque principal n'est pas le matériel, mais la couche de composition et de supervision.

Le système actuel est un ensemble de skills isolées. Le niveau suivant requis est un orchestrateur intelligent capable de :
- décider quelles skills déclencher ;
- gérer le flux d'exécution ;
- surveiller les conditions de succès / échec ;
- sécuriser le robot en permanence.

## 1.5 Exemple de skills nécessaires pour les tâches ciblées

### Cas 1 : "suit la balle rouge"
Skills requises :
- capture_video
- detect_red_ball
- estimate_target_position
- align_toward_target
- move_forward_toward_target
- track_target_continuously
- stop_when_target_lost
- emergency_stop_if_obstacle

### Cas 2 : "fait un rond"
Skills requises :
- set_motion_mode(circular)
- drive_arc_left_or_right
- maintain_turn_rate
- measure_progress_by_time_or_distance
- stop_when_circle_completed
- monitor_obstacle

## 1.6 Conclusion

Le robot a bien une base de skills. La prochaine étape ne consiste pas à créer encore un autre capteur ou moteur, mais à formaliser le niveau supérieur : les compétences de composition, d'orchestration, de boucle de suivi et de sécurité.
