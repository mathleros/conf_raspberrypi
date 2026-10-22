# Contexte du projet Raspberry Pi / iRobot

Ce document synthétise l'ensemble du contexte du dépôt afin de rendre les échanges futurs plus efficaces. Il a été construit à partir de la lecture du code, des scripts d'installation, des tests et de la documentation du projet.

## 1. Objectif global

Le dépôt est un banc d'essai matériel pour Raspberry Pi 5 (et compatible Pi 4) centré sur :
- la caméra CSI
- le HAT ReSpeaker / micros / LEDs
- la motorisation Smart Car 2WD via L298N
- l'assistant vocal local hors ligne
- la validation de composants matériels de façon isolée

Le projet n'est pas un produit unique finalisé, mais plutôt une base d'expérimentation et de test : chaque composant est vérifié indépendamment, puis éventuellement réuni dans un système complet.

Le dépôt est donc plus proche d'un environnement de laboratoire / prototype embarqué qu'un projet applicatif classique.

## 2. Structure du dépôt

- `README.md` : référence principale, documentation d'installation et usage
- `pyproject.toml` : configuration Python / scripts `uv run`
- `scripts/` : scripts d'installation système + Bluetooth + LLM
- `src/irobot/` : modules Python du projet
- `tests/` : scripts de test matériel
- `docs/` : guides complémentaires
- `commandes.txt` : commandes utiles / dépannage

### Arborescence utile

- `src/irobot/camera/camera_live.py` : flux vidéo en direct
- `src/irobot/camera/balle_rouge.py` : détection d'une balle rouge par OpenCV
- `src/irobot/smart_car/smart_car.py` : contrôle de la voiture 2WD
- `src/irobot/voice_assistant/voice_assistant.py` : transcribe la voix + contrôle vocal de la voiture + appel LLM local
- `tests/gpio_test.py` : activation des GPIO
- `tests/led_test.py` : test des LEDs APA102 du HAT ReSpeaker
- `tests/micro_test.py` : test des micros WM8960 et enregistrement WAV

## 3. Stack logicielle

### Python
- Python >= 3.12
- `uv` utilisé pour le gestionnaire de dépendances et les scripts

### Dépendances principales
Dans `pyproject.toml` :
- `opencv-python`
- `requests`
- `vosk`
- `gpiozero`

### Outils système
- `picamera2` (via apt)
- `llama.cpp` / `llama-server`
- `Vosk` pour la transcription vocale
- `alsa-utils`, `bluetooth`, `pulseaudio`, `bluez`, etc.

## 4. Composants matériels supportés

### 4.1 Raspberry Pi
- Raspberry Pi 5 (référence principale)
- Compatible Pi 4 / CM4 / CM5 en théorie
- Système cible : Raspberry Pi OS 64 bits (Debian Bookworm ou plus récent)

### 4.2 Caméra
- Caméra CSI OV5647 InnoMaker CAM-OV5647
- Détection via `Picamera2`
- Cas particulier : si la caméra n'est pas auto-détectée, il faut parfois forcer :
  `dtoverlay=ov5647,cam1`

### 4.3 HAT ReSpeaker / audio / mic / LEDs
- Modèle : Keyestudio ReSpeaker 2-Mic Pi HAT V1.0
- Code audio : WM8960
- 2 micros
- sortie audio 3.5 mm
- 3 LEDs APA102
- bouton GPIO17

### 4.4 Smart Car 2WD
- moteur 2 roues
- pont H-bridge L298N
- GPIO BCM utilisés :
  - IN1 = GPIO 5
  - IN2 = GPIO 6
  - IN3 = GPIO 16
  - IN4 = GPIO 24
  - ENA = GPIO 12
  - ENB = GPIO 13

### 4.5 GPS / GNSS
Le README mentionne aussi un HAT Waveshare u-blox MAX-M10S, mais ce n’est pas central dans le code présent. C’est un composant potentiel, mais le code actuel ne montre pas d’implémentation GPS active dans le dépôt.

### 4.6 Capteur de distance HC-SR04
Le projet intègre désormais un module de test pour un capteur ultrason HC-SR04.

Important : le HC-SR04 ne nécessite pas de script d’installation spécifique. Il repose sur la configuration GPIO déjà fournie par le projet via `scripts/install_rpigpio.sh`.

Donc, pour ce capteur :
- il faut d’abord installer le support GPIO avec `sudo ./install_rpigpio.sh`
- ensuite seulement on branche le HC-SR04 sur les GPIO adéquats
- le vrai point de configuration est le câblage GPIO, pas un script dédié d’installation

GPIO recommandés :
- TRIG -> GPIO 17 (broche physique 11)
- ECHO -> GPIO 27 (broche physique 13)
- GND -> broche physique 6 (masse du Raspberry Pi)
- VCC -> broche physique 4 (5V du Raspberry Pi)

Le module Python associé est :
- `src/irobot/sensors/hc_sr04.py`

Le test prévu est :
- afficher la distance du premier objet détecté devant le capteur

### Règle de robustesse GPIO

Pour tous les scripts utilisant `gpiozero` sur Raspberry Pi, il faut appliquer cette règle systématiquement :
- fermer proprement les périphériques GPIO (`close()`)
- puis quitter immédiatement avec `os._exit(0)` après le nettoyage

Cela évite un crash Python au moment du shutdown sur certains Raspberry Pi, même quand la logique métier a bien fonctionné.

## 5. Architecture logicielle

### 5.1 Module caméra
`camera_live.py`
- utilise `Picamera2.global_camera_info()` pour détecter les caméras
- ouvre le flux vidéo
- affiche la fenêtre OpenCV `Camera 1 - Live`
- boucle jusqu’à appui sur `q`

`balle_rouge.py`
- transforme le flux en HSV
- applique un masque rouge (deux plages autour du rouge)
- nettoie morphologiquement l’image
- détecte contours
- garde la plus grosse zone rouge
- dessine un rectangle et un label `BALLE ROUGE DETECTEE`

Ce script est un test de vision, pas un module de production de robot autonome.

### 5.2 Module voiture Smart Car
`smart_car.py`
- encapsule `SmartCar2WD`
- crée des `DigitalOutputDevice` pour les directions IN1/IN2/IN3/IN4
- crée des `PWMOutputDevice` pour ENA/ENB
- supporte :
  - `forward`
  - `backward`
  - `left`
  - `right`
  - `stop`

Contrôle de vitesse :
- `set_speed()` avec clamp 0.0 à 1.0
- PWM sur ENA / ENB
- `cleanup()` pour fermer proprement les GPIO

### 5.3 Module assistant vocal
`voice_assistant.py`
Le module regroupe plusieurs fonctions :
- détection de la source audio (`auto`, `bluetooth`, `wm8960`, `default`)
- capture du microphone via `arecord`
- transcription par Vosk
- appels LLM local via HTTP à `http://127.0.0.1:8080/v1/chat/completions`
- contrôle vocal de la voiture via commandes françaises / anglaises

Fonctionnement clé :
- `transcribe_loop(device)` lit les échantillons audio brute et les envoie au moteur Vosk
- `ask_llm(text)` envoie le texte à `llama-server`
- `VoiceCarController.handle_text(text)` interprète les commandes vocales pour piloter la voiture

Commandes voz reconnues incluent par exemple :
- `avance`, `avancer`, `go forward`, `forward`
- `recule`, `reculer`, `go back`, `backward`
- `tourne à gauche`, `turn left`, `left`
- `tourne à droite`, `turn right`, `right`
- `stop`, `arrêt`
- `va plus vite`, `go faster`, etc.

Le système supporte également :
- durée implicite ou explicite (`pendant 2 secondes`, `for 3 sec`)
- vitesse de base via `--car-speed 0.5`
- commande `--once`
- `--no-llm` pour exécuter uniquement la transcription

## 6. Commandes principales du projet

Les scripts exposés via `pyproject.toml` sont :
- `camera-live`
- `balle-rouge`
- `voice-assistant`
- `smart-car`

Exemples :

```bash
uv run camera-live
uv run balle-rouge
uv run micro-test
uv run led-test static red green blue
uv run gpio-test 5 6 16 24 --duration 0.5
uv run smart-car forward --duration 1
uv run voice-assistant --once
uv run voice-assistant --car --input-device bluetooth
```

## 7. Scripts de test matériels

### `tests/gpio_test.py`
- active des GPIO précis
- sert à valider le câblage du pont H-bridge / moteur

### `tests/led_test.py`
- utilise SPI sur `/dev/spidev0.1`
- prend les modes :
  - `static`
  - `scan`
  - `rainbow`
  - `off`

### `tests/micro_test.py`
- détecte la carte WM8960 via `arecord -l`
- enregistre 5 secondes d’audio en WAV
- affiche niveaux L/R en temps réel
- rejoue le fichier avec `aplay`

### `tests/distance_test.py`
Un test de mesure de distance a été ajouté dans le dossier `tests/`.

- fichier : `tests/distance_test.py`
- objectif : afficher la distance du premier objet détecté devant le capteur
- GPIO par défaut : TRIG=17, ECHO=27
- durée par défaut : 5 secondes
- comportement similaire à `tests/micro_test.py` : affichage en direct avec mesure et statistiques finales

## 8. Scripts d'installation système

### `scripts/install_rpigpio.sh`
- vérifie que l’on est sur un Raspberry Pi
- installe `python3-gpiozero`
- prépare le système pour l’utilisation des GPIO

### `scripts/install_respeaker.sh`
- configure les overlays `wm8960-soundcard` et SPI
- installe `alsa-utils`, `i2c-tools`, etc.
- télécharge `/etc/wm8960-soundcard/wm8960_asound.state`
- crée un service `systemd` pour restaurer les paramètres audio au boot

### `scripts/install_llm.sh`
- installe les dépendances système de compilation
- clone `llama.cpp`
- compile `llama-server`
- télécharge le modèle `Ministral 3 3B` en GGUF
- installe le modèle Vosk français
- configure le service `ministral.service`
- lance `uv sync --project` côté utilisateur

### `scripts/install_bluetooth_audio.sh`
- installe `bluez`, `pulseaudio`, `alsa-utils`
- active le service Bluetooth
- configure un helper de diagnostic pour les sources audio Bluetooth

### `scripts/connect_jabra_bt.sh`
- scan Bluetooth
- appairage / connexion à un casque Jabra
- vérifie les sources audio disponibles

## 9. Installation recommandée

Le README et les scripts suggèrent généralement ce flux :

1. installer Raspberry Pi OS 64 bits
2. activer SSH
3. mettre à jour le système
4. installer le support GPIO
5. installer le ReSpeaker si besoin
6. installer le support Bluetooth audio si besoin
7. installer `llama.cpp` + modèle local + Vosk
8. lancer le système de test ou la commande vocale

## 10. Modèle LLM local

Le projet vise un fonctionnement local, sans dépendance à un cloud.

- `llama-server` écoute sur `127.0.0.1:8080`
- API compatible OpenAI : `/v1/chat/completions`
- modèle choisi : `Ministral 3 3B` (ou variante alignée)
- le modèle est utilisé pour générer des réponses à partir de la transcription

En pratique :
- le flux audio -> Vosk -> texte
- texte -> llama-server -> réponse dans le terminal
- si mode `--car`, le LLM n’est pas forcément utilisé, mais la logique de commande est directement gérée dans le contrôleur vocal Python

## 11. Points de vigilance / pièges connus

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

## 12. Hypothèses de conception

Le dépôt montre clairement une logique de preuve de concept / validation physique :
- chaque module est testable séparément
- le but n’est pas d’avoir un backend robuste ou un produit prêt pour la production
- le code est orienté démonstration, expérimentation et prototypage embarqué

## 13. Points importants pour les échanges futurs

Quand on travaille sur ce projet, il faut garder à l’esprit que :
- la plupart des composants exigent un environnement Raspberry Pi réel
- la majorité des scripts sont basés sur des interfaces système (GPIO, ALSA, SPI, Bluetooth, système file)
- le code est très dépendant du matériel
- des erreurs peuvent venir de l’OS, de la configuration du device tree, des overlays, ou des dépendances apt
- le projet repose sur `uv` et sur les outils système installés par les scripts

## 14. Règle de maintenance du contexte

Le fichier `PROJECT_CONTEXT.md` est un document vivant et doit être mis à jour systématiquement dès que l’on apprend une information utile, un changement de configuration, une évolution de l’architecture, un nouveau composant, un correctif ou une convention de travail.

Règle de travail :
- si une donnée est nouvelle ou modifie le contexte du projet, elle doit être ajoutée ici
- si un comportement réel diffère du contexte documenté, ce dernier doit être corrigé
- si une commande, un script ou une convention importante est découverte, elle doit être intégrée
- le contexte ne doit pas rester figé tant que le projet évolue

Objectif : garantir que la mémoire du projet reste exacte, exploitable et cohérente d’une conversation à l’autre.

## 15. Conclusion

Ce dépôt est un environnement de démonstration / laboratoire sur Raspberry Pi dédié à :
- la commande matérielle locale
- la vision par caméra
- la commande vocale hors ligne
- la voiture autonome de prototype

Le code est compréhensible et modulaire, mais il dépend fortement du contexte matériel et système. Pour toute modification future, il faut toujours se référer à la fois au code Python et au contexte logiciel système (GPIO, ALSA, SPI, Bluetooth, `llama-server`, `systemd`, device tree).

Ce document sert comme base de contexte pour travailler plus vite et plus correctement sur les prochaines itérations.
