# 2. Étude d'architecture fonctionnelle et technique

## 2.1 Objectif fonctionnel

Le système doit exécuter une instruction vocale complexe et produire un comportement robotique autonome, en respectant la sécurité, en s'appuyant sur les compétences existantes et en gardant une logique de contrôle explicite.

Exemples de commande vocale :
- "suit la balle rouge"
- "fait un rond"
- "avance jusqu'à l'objet rouge puis tourne à gauche"
- "évite les obstacles et continue la cible"

## 2.2 Principe directeur

L'architecture cible repose sur 5 niveaux :
1. capture audio / perception
2. transcription / compréhension du langage
3. planification / orchestration
4. exécution de skills
5. supervision / sécurité / feedback

Aucun bloc ne doit piloter les moteurs de manière libre. L'acquisition d'un ordre est toujours convertie en structure interne avant exécution.

## 2.3 Architecture fonctionnelle

### Bloc 1. Entrée utilisateur / audio

Composants :
- casque Bluetooth
- microphone ReSpeaker WM8960
- sélection de source audio

Responsabilités :
- capter la voix de l'utilisateur
- choisir le bon périphérique selon contexte (Bluetooth / ReSpeaker / default)
- fournir un flux audio brut

Données produites :
- flux audio brut ou fichier WAV

### Bloc 2. Transcription vocale

Composants :
- Vosk / modèle FR
- adapté au projet actuel

Responsabilités :
- convertir le flux audio en texte en français
- gérer la détection de fin de phrase
- délivrer une phrase lisible pour le LLM

Sortie :
- texte brut : "suit la balle rouge" ou "tourne à droite pendant 3 secondes"

### Bloc 3. Compréhension de l'intention

Composants :
- LLM local ou externe
- wrapper d'inférence
- convertisseur texte -> structure JSON

Responsabilités :
-classer la commande comme task, action, stop condition, object target, etc.
- extraire l'objectif et les paramètres
- sélectionner les skills pertinentes
- produire une structure structurée

Sortie attendue :
- objet JSON ou dictionnaire Python, par exemple :

```json
{
  "task": "follow_target",
  "target": "red_ball",
  "strategy": "visual_track",
  "speed": 0.5,
  "max_duration": 20,
  "stop_conditions": ["target_lost_for_3s", "obstacle_too_close", "manual_stop"],
  "skills": [
    "detect_red_ball",
    "align_to_target",
    "approach_target",
    "track_target"
  ]
}
```

### Bloc 4. Orchestrateur / planner

Composants :
- `MissionPlanner`
- `SkillOrchestrator`
- `TaskStateMachine`

Responsabilités :
- lire le plan LLM
- vérifier la validité de la commande
- sélectionner les actions à exécuter
- gérer l'ordre des skills
- influer sur les conditions de boucle
- observer les retours d'état

Sortie :
- séquence d'actions sur le robot

### Bloc 5. Skills exécutables

Chaque skill est un objet avec une interface standard :
- nom
- entrée
- préconditions
- sortie
- statut success / error / retry / timeout

Exemples :
- `detect_red_ball` -> retourne position `centre`, `gauche`, `droite`, ou `none`
- `align_to_target` -> applique un mouvement de correction d'orientation
- `approach_target` -> avance progressivement si cible visible et espacé
- `track_target` -> boucle de correction visuelle
- `move_circular` -> génère un mouvement circulaire
- `stop_motion` -> arrêt immédiat

### Bloc 6. Capteurs / perception robotique

Composants :
- caméra Raspberry Pi
- capteur ultrason HC-SR04
- éventuellement future perception moteur / odométrie

Responsabilités :
- produire un état du monde du robot
- alimenter les boucles de contrôle et de sécurité

### Bloc 7. Actionneurs

Composants :
- Smart Car 2WD / pont L298N
- moteurs gauche / droite

Responsabilités :
- produire un mouvement physique
- appliquer les consignes de vitesse, direction et durée

### Bloc 8. Sécurité / supervision

Composants :
- guard / watchdog
- vérification d'obstacle
- arrêt d'urgence
- temporisation de taches

Responsabilités :
- interrompre toute action dangereuse
- réajuster le plan si la cible disparaît
- garantir un arrêt propre

## 2.4 Flux global de la commande

Flux texte :
- utilisateur parle -> Bluetooth
- transcription -> texte
- texte -> LLM -> plan structurée
- plan -> orchestrateur
- orchestrateur -> skills
- skills -> capteurs
- capteurs -> état
- état -> décision / continue / stop

## 2.5 Contrat d'interface des skills

Chaque skill devrait exposer une API cohérente :

```python
class RobotSkill:
    name: str
    description: str
    params: dict
    def execute(self, context: dict) -> dict:
        pass
```

Sortie standard :

```json
{
  "status": "success|running|failed|timeout",
  "message": "explanation",
  "data": { "position": "centre", "distance_cm": 22.5 },
  "confidence": 0.82,
  "next_action": "align_to_target"
}
```

Cette structure permet au planificateur de décider de la suite sans dépendre d'une sortie textuelle libre.

## 2.6 Architecture technique proposée

### Répartition logicielle

- `src/irobot/voice_assistant/`
  - capture audio
  - STT
  - LLM wrapper
  - commande vocale simple

- `src/irobot/camera/`
  - détection visuelle
  - tracking
  - position cible

- `src/irobot/smart_car/`
  - moteur / roues / direction / vitesse

- `src/irobot/sensors/`
  - capteur HC-SR04

- `src/irobot/skills/` (nouveau module) :
  - `base_skill.py`
  - `follow_target.py`
  - `move_circle.py`
  - `obstacle_avoidance.py`
  - `align_to_target.py`
  - `stop_motion.py`

- `src/irobot/orchestrator/` (nouveau module) :
  - `planner.py`
  - `state_machine.py`
  - `executor.py`
  - `security.py`

### Découpage fonctionnel

- couche I/O
  - audio
  - caméra
  - GPIO / moteur

- couche contexte
  - état robot
  - position observée
  - cible détectée
  - obstacles

- couche décision
  - LLM planifier
  - planner déterministe
  - règles de sécurité

## 2.7 Règles d'architecture à respecter

1. Ne jamais laisser le LLM piloter directement les moteurs.
2. Toujours transformer la commande naturelle en plan structuré.
3. Vérifier les préconditions avant l'exécution d'une skill.
4. Chaque skill doit être observable et stoppable.
5. Un robot autonome doit avoir une garde-fou sur obstacle et sur durée de mission.
6. Le LLM doit être utilisé comme générateur de plan, pas comme moteur de contrôle temps réel.

## 2.8 Cas d'usage cibles et planification associée

### Cas 1 : "suit la balle rouge"
Plan type :
- `detect_red_ball`
- `estimate_position`
- `align_to_target`
- `approach_target`
- `track_target_until_lost`
- `stop_when_lost_or_cancelled`

### Cas 2 : "fait un rond"
Plan type :
- `start_circle_motion`
- `maintain_turn_rate`
- `monitor_elapsed_time_or_path`
- `stop_cycle_completed`

## 2.9 Conclusion

Le projet est prêt pour un saut d'abstraction : il faut un layer orchestration, un planner déterministe, et une représentation explicite des skills. C'est ce qui permettra de passer d'une base de tests matériels à un robot réellement guidé par une instruction vocale complexe.
