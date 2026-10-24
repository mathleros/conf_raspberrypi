# Contexte du projet Raspberry Pi / iRobot

Ce document synthétise l'ensemble du contexte du dépôt afin de rendre les échanges futurs plus efficaces. Il a été construit à partir de la lecture du code, des scripts d'installation, des tests et de la documentation du projet.

## 1. Objectif global

Le dépôt est un banc d'essai matériel pour Raspberry Pi 5 (et compatible Pi 4) centré sur :
- la caméra CSI
- le HAT ReSpeaker / micros / LEDs
- la motorisation Smart Car 2WD via L298N
- l'assistant vocal local hors ligne
- la validation de composants matériels de façon isolée
- la commande du robot par texte ou voix via un système d'intentions et de skills

Le projet n'est pas un produit unique finalisé, mais plutôt une base d'expérimentation et de test : chaque composant est vérifié indépendamment, puis éventuellement réuni dans un système complet.

Le dépôt est donc plus proche d'un environnement de laboratoire / prototype embarqué qu'un projet applicatif classique.

## 2. Évolution de l'architecture

Le projet a été ref

- `domain/` : logique métier du robot
  - skills : primitives, perception, behaviors
  - orchestrator : planification et exécution
- `interfaces/` : points d'entrée et adaptateurs entre langage / robot / matériel
  - parsing de texte / voix en `Intent`
  - contrôleur de langage `LanguageController`
  - adaptateur robot `RobotController`
- `hardware/` : drivers et modules concrets
  - camera
  - smart_car
  - sensors
  - audio

Le principe central est le suivant :
- la demande utilisateur est convertie en intention (`Intent`)
- cette intention est validée puis transformée en plan de skills
- le plan est exécuté par `SkillExecutor`
- les skills appelent `RobotController`, qui adapte la logique au matériel
- le LLM n'exécute pas directement les GPIO

## 3. Structure du dépôt

- `README.md` : référence principale, documentation d'installation et usage
- `pyproject.toml` : configuration Python / scripts `uv run`
- `scripts/` : scripts d'installation système + Bluetooth + LLM
- `src/irobot/` : modules Python du projet
- `tests/` : scripts de test matériel et unitaires
- `tests/unit/` : tests unitaires de logique métier
- `tests/hardware/` : scripts de validation sur le matériel réel
- `docs/` : guides complémentaires
- `commandes.txt` : commandes utiles / dépannage

### Arborescence utile

- `src/irobot/domain/skills/perception/detect_object.py` : skill de détection d'objet
- `src/irobot/domain/skills/behaviors/follow_target.py` : suite d'une cible
- `src/irobot/domain/orchestrator/planner.py` : mapping des intentions vers les skills
- `src/irobot/interfaces/intent_parser.py` : parsing du langage naturel en `Intent`
- `src/irobot/interfaces/language_controller.py` : pipeline texte → intention → plan → exécution
- `src/irobot/hardware/camera/color_detector.py` : détecteur de couleur par OpenCV (rouge/jaune)
- `src/irobot/hardware/smart_car/smart_car.py` : contrôle de la voiture 2WD
- `src/irobot/hardware/audio/voice_assistant.py` : transcription + LLM local + commandes vocales

### Règle de structure : scripts et tests

Le dépôt suit une organisation stricte pour éviter la confusion entre installation, validation locale et tests automatisés :

- `scripts/install/` : scripts d'installation système, dépendances, matériel, LLM, Bluetooth, etc.
- `scripts/test/` : scripts de validation locale, de runtime, de démonstration sans matériel réel, et de test d'environnement
- `tests/` : tests automatisés Python (`pytest`) pour le code métier, le hardware et les intégrations pertinentes

Règles à respecter :
- ne pas mélanger les scripts d'installation avec les scripts de test
- maintenir les scripts de démonstration locale dans `scripts/test/`
- garder les tests automatisés dans `tests/` et leur nommage dans le style `test_*.py`
- utiliser des noms explicites et cohérents (`install_llm_mac_portable.sh`, `run_llm_runtime_mac.sh`, `test_voice_runtime.py`)
- distinguer clairement : installation de dépendances / validation de l'environnement / tests de qualité
- pour les environnements macOS Intel, privilégier la solution portable sans Homebrew (`scripts/install/install_llm_mac_portable.sh`)

Cette règle évite la confusion entre :
- configuration système
- validation fonctionnelle locale
- tests de qualité automatisés

## 4. Stack logicielle

### Python
- Python >= 3.12
- `uv` utilisé pour le gestionnaire de dépendances et les scripts

### Dépendances principales
Dans `pyproject.toml` :
- `opencv-python`
- `requests`
- `vosk`
- `gpiozero`
- `pytest`

### Outils système
- `picamera2` (via apt)
- `llama.cpp` / `llama-server`
- `Vosk` pour la transcription vocale
- `alsa-utils`, `bluetooth`, `pulseaudio`, `bluez`, etc.
- sur macOS Intel, la voie d'installation retenue est la version portable sans Homebrew : `scripts/install/install_llm_mac_portable.sh`

## 5. Architecture fonctionnelle du langage robotique

### 5.1 Entrée manuscrite / vocale
Le système accepte au moins deux sources d'entrée :
- une phrase naturelle en texte
- une commande vocale capturée via microphone + Vosk

### 5.2 Parsing des intentions
Le module `IntentParser` transforme le texte brut en objet métier :

```python
Intent(
    name="follow_red_ball",
    target="red_ball",
    parameters={"speed": 0.5},
    confidence=0.9,
    raw_text="va vers la balle rouge"
)
```

Ce parsing a deux objectifs :
- normaliser la commande pour la machine
- sécuriser la commande en limitant les intentions autorisées

### 5.3 Validation et garde-fous
`IntentValidator` autorise uniquement un sous-ensemble d'intentions :
- `follow_red_ball`
- `avoid_obstacle`
- `move_forward`
- `move_backward`
- `turn_left`
- `turn_right`
- `stop`

Cela évite qu'une commande non contrôlée ou ambiguë ne déclenche des actions dangereuses.

### 5.4 Planification
`SkillPlanner` associe chaque intention à une séquence de skills. Exemple :

```python
"follow_red_ball": [
    "detect_object",
    "follow_target",
    "detect_obstacle",
    "stop_motion",
]
```

Le plan est explicite et déterministe. Le LLM ne décide pas directement des GPIO, il produit seulement une intention.

### 5.5 Exécution
`SkillExecutor` exécute les skills de manière structurée, en passant un `SkillContext` partagé :
- `robot`
- `camera`
- `sensor`
- `state`

Chaque skill retourne un `SkillResult` comprenant :
- `status`
- `message`
- `data`
- `confidence`
- `next_action`

## 6. Skills du robot

### 6.1 Primitives
- `move_forward`
- `move_backward`
- `turn_left`
- `turn_right`
- `stop_motion`

### 6.2 Perception
- `detect_object`
- `detect_obstacle`

### 6.3 Behaviors
- `follow_target`
- `move_circle`

Cette séparation est importante :
- primitives = actions atomiques sur le robot
- perception = lecture du monde
- behaviors = logique composite de haut niveau

## 7. Commandes principales du projet

Les scripts exposés via `pyproject.toml` sont :
- `camera-live`
- `color-detector` (alias historique : `balle-rouge`)
- `voice-assistant`
- `smart-car`

Exemples :

```bash
uv run camera-live
uv run color-detector
uv run color-detector --color yellow
uv run micro-test
uv run led-test static red green blue
uv run gpio-test 5 6 16 24 --duration 0.5
uv run smart-car forward --duration 1
uv run voice-assistant --once
```

## 8. Côté robot autonome

Le système est désormais structuré pour qu'une phrase naturelle déclenche un séquençage intelligent de skills.

Exemple de comportement :

```text
Texte : "va vers la balle rouge"
→ Intent(name="follow_red_ball", target="red_ball")
→ Plan : detect_object → follow_target → detect_obstacle → stop_motion
→ Exécution contrôlée par SkillExecutor
```

Le LLM, s'il est utilisé, doit être traité comme un interprète de langage, pas comme un pilote direct de GPIO.

## 9. Scripts de test matériels

### `tests/hardware/test_hardware_gpio.py`
- active des GPIO précis
- sert à valider le câblage du pont H-bridge / moteur

### `tests/hardware/test_hardware_led.py`
- utilise SPI sur `/dev/spidev0.1`
- prend les modes :
  - `static`
  - `scan`
  - `rainbow`
  - `off`

### `tests/hardware/test_hardware_micro.py`
- détecte la carte WM8960 via `arecord -l`
- enregistre 5 secondes d’audio en WAV
- affiche niveaux L/R en temps réel
- rejoue le fichier avec `aplay`

### `tests/hardware/test_hardware_distance.py`
- fichier : `tests/hardware/test_hardware_distance.py`
- objectif : afficher la distance du premier objet détecté devant le capteur
- GPIO par défaut : TRIG=17, ECHO=27
- durée par défaut : 5 secondes

## 10. Scripts d'installation système

### `scripts/install_rpigpio.sh`
- vérifie que l’on est sur un Raspberry Pi
- installe `python3-gpiozero`
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
- configure le service `ministral.service`

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
