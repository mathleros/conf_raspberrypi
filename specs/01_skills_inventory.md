# 1. Inventaire des skills existants et des écarts

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

## 1.3 Compétences manquantes ou insuffisamment formalisées

Voici les skills nécessaires pour réaliser les cas d'usage complexes décrits par le client.

### 1. `skill_registry`
- Description : système qui liste toutes les skills disponibles, leurs paramètres, leurs préconditions et leur contrat de sortie.
- État : absent
- Pourquoi c'est nécessaire : le LLM doit savoir exactement quelles actions sont disponibles et sous quel format il peut les utiliser.

### 2. `intent_parser`
- Description : transformer une consigne vocale en structure interne : objectif, cible, paramètres, conditions d'arrêt.
- État : incomplet
- Exemples :
  - objectif = follow_target
  - cible = red_ball
  - mode = continuous
  - stop_condition = target_lost_for_3s OR manual_stop

### 3. `plan_generator`
- Description : sélection d'un ensemble de skills dans un ordre logique.
- État : absent
- Exemple : `detect_red_ball -> align_with_target -> approach -> track`

### 4. `target_tracking_red_ball`
- Description : lire en continu la position de la balle rouge dans le champ visuel, calculer un écart horizontal / vertical et maintenir la cible au centre.
- État : partiellement présent au niveau de détection, mais pas sous forme de tracking boucle fermée

### 5. `target_approach_controller`
- Description : piloter le robot pour s'approcher de la cible sans collision.
- État : absent

### 6. `follow_target_loop`
- Description : boucle de suivi en temps réel : détecte la cible, décale le robot, corrige l'orientation, vérifie la présence de la cible, continue ou stoppe.
- État : absent

### 7. `trajectory_circle_controller`
- Description : génère un mouvement circulaire / rond, en maîtrisant vitesse et angle.
- État : absent

### 8. `state_machine_orchestrator`
- Description : machine d'états de mission : `idle -> planning -> executing -> success / failed / aborted`.
- État : absent

### 9. `safety_guard`
- Description : règle de sécurité permanente sur les obstacles et le moteur.
- État : partiellement présent via `check_obstacle`, mais pas encore intégré dans une logique globale d'évitement et d'urgence.

### 10. `mission_result_evaluator`
- Description : détermine si une tâche est réussie, en échec ou interrompue.
- État : absent

### 11. `execution_feedback_loop`
- Description : permet au système de mettre à jour l'état de la mission en fonction des observations du capteur et de la progression.
- État : absent

### 12. `structured_skill_output_contract`
- Description : chaque skill doit retourner une structure JSON ou un objet avec évaluation, action, diagnostic, confidence.
- État : absent

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
