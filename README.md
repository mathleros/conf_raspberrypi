# Raspberry Pi / iRobot playground

Ce dépôt est un banc d'essai robotique autour d'un Raspberry Pi : caméra, audio, capteurs, Smart Car 2WD, assistant vocal local et orchestration de skills.

Le projet a évolué vers une architecture plus claire :
- l'entrée texte / voix est transformée en `Intent`
- l'`Intent` est validée puis convertie en plan de `Skill`s
- le plan est exécuté par un orchestrateur
- le matériel n'est pas piloté directement par le LLM, mais via des skills et un adaptateur robot

## Architecture actuelle

```text
src/irobot/
├── domain/
│   ├── skills/
│   │   ├── primitives/
│   │   ├── perception/
│   │   ├── behaviors/
│   │   └── base_skill.py
│   └── orchestrator/
│       ├── planner.py
│       ├── registry.py
│       ├── executor.py
│       └── mission_state_machine.py
├── interfaces/
│   ├── intent_parser.py
│   ├── language_controller.py
│   ├── robot_controller.py
│   └── voice_runtime.py
├── hardware/
│   ├── audio/
│   ├── camera/
│   ├── sensors/
│   ├── smart_car/
│   └── ...
├── config/
└── __init__.py
```

Flux principal :

```text
Texte / voix
  ↓
IntentParser
  ↓
IntentValidator
  ↓
SkillPlanner
  ↓
SkillExecutor
  ↓
Skills / RobotController / hardware
```

## Structure du dépôt

```text
.
├── README.md
├── PROJECT_CONTEXT.md
├── pyproject.toml
├── docs/
│   ├── guide-installation-llm-local-pi5.md
│   └── guide-installation-llm-mac-portable.md
├── scripts/
│   ├── README.md
│   ├── install/
│   │   ├── install_llm_mac_portable.sh
│   │   ├── install_llm.sh
│   │   ├── install_respeaker.sh
│   │   ├── install_rpigpio.sh
│   │   ├── install_bluetooth_audio.sh
│   │   └── connect_jabra_bt.sh
│   └── test/
│       └── run_llm_runtime_mac.sh
├── src/
│   └── irobot/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── hardware/
└── target/
```

## Prérequis

- Raspberry Pi 5 recommandé (Pi 4 possible selon le matériel)
- Raspberry Pi OS 64 bits ; le guide LLM a été rédigé pour Raspberry Pi OS Bookworm
- Python >= 3.12
- Connexion réseau et environ 6 Go d'espace disque libre pour compiler llama.cpp et télécharger les modèles
- `uv` (installé à l'étape 3 ci-dessous)

### Scripts d'installation

Depuis la racine du dépôt, utiliser les scripts selon le matériel et la plateforme :

| Script | Fonction | Quand l'utiliser |
|---|---|---|
| [`install_rpigpio.sh`](scripts/install/install_rpigpio.sh) | Installe les dépendances système de `gpiozero` pour piloter le GPIO. | Sur le Raspberry Pi avant d'utiliser les composants matériels (moteurs, capteurs, etc.). |
| [`install_llm.sh`](scripts/install/install_llm.sh) | Compile `llama.cpp`, installe le modèle Qwen et Vosk, synchronise les dépendances Python et configure `llm.service`. | Sur le Pi pour installer le LLM local et le runtime vocal. |
| [`install_bluetooth_audio.sh`](scripts/install/install_bluetooth_audio.sh) | Installe BlueZ et les composants audio Bluetooth. | Sur le Pi si un casque Bluetooth, par exemple un Jabra, sert de microphone. |
| [`connect_jabra_bt.sh`](scripts/install/connect_jabra_bt.sh) | Recherche, appaire et connecte le casque Bluetooth. | Après l'installation Bluetooth, pour associer le casque choisi au Pi. |
| [`install_respeaker.sh`](scripts/install/install_respeaker.sh) | Configure l'overlay audio et les outils du HAT ReSpeaker 2-Mic. | Sur le Pi avec le HAT ReSpeaker connecté, en alternative au casque Bluetooth. Un redémarrage est nécessaire. |
| [`install_llm_mac_portable.sh`](scripts/install/install_llm_mac_portable.sh) | Installe le LLM portable pour les tests locaux sans Homebrew. | Sur macOS uniquement ; ne configure pas le matériel du Raspberry Pi. |

## Installation et configuration sur Raspberry Pi

### 1. Préparer Raspberry Pi OS

Avec Raspberry Pi Imager, installer Raspberry Pi OS 64 bits et configurer un utilisateur, le réseau Wi-Fi et SSH si le Pi sera administré à distance. Démarrer le Pi, se connecter avec cet utilisateur, puis mettre le système à jour :

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

Après le redémarrage, se reconnecter et installer les outils de base :

```bash
sudo apt install -y git curl
```

### 2. Récupérer le projet

Cloner le dépôt de l'équipe (remplacer `<URL_DU_DEPOT>` par son URL), ou copier le projet sur le Pi :

```bash
git clone <URL_DU_DEPOT> ~/conf_raspberrypi
cd ~/conf_raspberrypi
```

Exécuter les commandes suivantes depuis la racine `conf_raspberrypi`.

### 3. Installer uv

Le script d'installation du LLM lance `uv sync` pour installer le projet et ses dépendances Python. Installer `uv` pour l'utilisateur courant :

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
uv python install 3.12
uv --version
```

Cette commande installe aussi Python 3.12, requis par le projet même si la version fournie par le système est plus ancienne. Si `uv` n'est pas trouvé après l'installation, ouvrir un nouveau terminal ou ajouter `~/.local/bin` au `PATH`.

### 4. Installer le support GPIO

Cette étape installe les paquets système nécessaires à `gpiozero` sur le Pi :

```bash
sudo ./scripts/install/install_rpigpio.sh
```

### 5. Installer le LLM et le runtime vocal

L'installateur compile `llama.cpp` pour le Pi, télécharge Qwen2.5-1.5B-Instruct (GGUF Q4_K_M) et le modèle Vosk français, installe les dépendances Python du projet, puis configure `llm.service` pour démarrer au boot. Le téléchargement et la compilation nécessitent une connexion Internet et plusieurs Go d'espace disque.

```bash
sudo ./scripts/install/install_llm.sh
```

Démarrer le serveur LLM et vérifier son état et son API locale :

```bash
sudo systemctl start llm.service
sudo systemctl status llm.service --no-pager
curl http://127.0.0.1:8080/v1/models
```

Le chargement initial du modèle peut prendre 20 à 30 secondes. Pour consulter les journaux ou gérer le service :

```bash
journalctl -u llm.service -f
sudo systemctl restart llm.service
sudo systemctl stop llm.service
```

Le service est activé au démarrage par l'installateur. Pour essayer l'assistant vocal sur le Pi une fois le microphone configuré, lancer `uv run voice-runtime` depuis la racine du projet (Ctrl+C pour quitter).

### 6. Configurer le matériel et les paramètres du runtime

Choisir et installer **une** configuration micro selon le matériel :

```bash
# Casque Bluetooth (optionnel)
sudo ./scripts/install/install_bluetooth_audio.sh
sudo reboot
./scripts/install/connect_jabra_bt.sh scan
./scripts/install/connect_jabra_bt.sh <ADRESSE_MAC_DU_CASQUE>
bluetoothctl info <ADRESSE_MAC_DU_CASQUE>
uv run voice-assistant --once --input-device bluetooth
```

Pour le HAT **ReSpeaker 2-Mic** à la place du casque Bluetooth :

```bash
sudo ./scripts/install/install_respeaker.sh
sudo reboot
aplay -l
arecord -l
uv run voice-assistant --once --input-device wm8960
```

Le ReSpeaker requiert le HAT connecté avant le redémarrage pour charger son overlay audio. Les scripts Bluetooth et ReSpeaker ne sont pas nécessaires pour le runtime texte/LLM.

Les paramètres du robot et de la perception sont dans [config/runtime_calibration.toml](config/runtime_calibration.toml). Après installation et branchement de la caméra, calibrer si nécessaire la focale avec `uv run calibrate-distance --known-distance-cm 100`, puis reporter la valeur `focal_px` affichée dans la section `[camera]` du fichier. Garder `ultrasonic_fusion = false` tant que le capteur ultrason n'est pas installé et validé.

**Sécurité matériel :** avant tout essai susceptible de commander les moteurs, placer le robot sur un support stable avec les roues dégagées, puis vérifier l'arrêt d'urgence et le câblage.

### Installation et tests sur macOS

Pour installer le LLM portable sur Mac et tester le pipeline sans microphone ni matériel robot :

```bash
cd /path/to/conf_raspberrypi
bash scripts/install/install_llm_mac_portable.sh
bash scripts/test/run_llm_runtime_mac.sh --text "va vers la balle rouge"
```

Pour lancer la validation complète du runtime Mac :

```bash
bash scripts/test/run_llm_runtime_mac.sh
```

Cette commande démarre le serveur local et valide le pipeline texte -> `Intent` -> skills.

### LLM et runtime sur Raspberry Pi

Le Pi sert **Qwen2.5-1.5B-Instruct** quantisé **Q4_K_M** (~1,1 Go) via `llama-server`, sur `127.0.0.1:8080` (alias `qwen2.5-1.5b`, contexte 2048). Pour les étapes d'installation manuelle, les réglages de performance ou le dépannage avancé, voir [docs/guide-installation-llm-local-pi5.md](docs/guide-installation-llm-local-pi5.md).

Fonctionnement du runtime (`voice_runtime.py`) :
- la transcription est normalisée de façon déterministe (nombres en lettres -> chiffres, minutes -> secondes, mètres -> centimètres) ;
- les commandes d'arrêt (« stop », « arrête toi », « halte », « pause ») sont traitées localement, sans LLM ;
- le plan LLM est contrôlé lexicalement ; toute intention ou valeur numérique non justifiée par la phrase est rejetée ;
- en cas de timeout, d'erreur HTTP, de JSON invalide ou de réponse incomplète, le parseur local prend le relais ; une liste d'étapes vide est rejetée.

Variables d'environnement (défauts) : `LLM_MODEL` (`qwen2.5-1.5b`), `LLM_CONNECT_TIMEOUT_SECONDS` (1.0), `LLM_READ_TIMEOUT_SECONDS` (10.0), `LLM_MAX_TOKENS_PLAN` (120), `LLM_MAX_TOKENS_INTENT` (96), `LLM_RESPONSE_FORMAT` (`schema` ; ou `json_object`, `none`), `LLM_WARMUP_WAIT_SECONDS` (60, attente du préchauffage en `--once`/`--text`). Diagnostic dans l'événement `plan_raw` de la trace : `llm_latency_seconds`, `llm_response_format`, `llm_attempts`, `llm_prompt_tokens`, `llm_completion_tokens`, `llm_timings`, `error_type`, `warmup_status`. Évaluation du prompt sur le serveur : `python3 scripts/test/eval_prompt_plan.py --repeat 3`.

## Commandes utiles

### Caméra

```bash
uv run camera-live
uv run color-detector
# Sur Pi : balle jaune centrée à 100 cm mesurés depuis la caméra
uv run calibrate-distance --color yellow --ball-diameter-cm 6.5 --known-distance-cm 100
# Après avoir reporté focal_px dans [camera], vérifier l'estimation en direct
uv run calibrate-distance --color yellow
```

`calibrate-distance` prend 30 mesures par défaut (`--samples` pour changer ce nombre) et affiche la focale à reporter manuellement dans [config/runtime_calibration.toml](config/runtime_calibration.toml). Renseigner aussi le diamètre réel `ball_diameter_cm` dans ce fichier. La distance visuelle est estimée par `focal_px * ball_diameter_cm / diameter_px`, puis lissée dans la perception live. La fusion ultrason reste optionnelle (`ultrasonic_fusion = false` par défaut), uniquement pour une cible centrée et des mesures cohérentes à ±25 %.

### Smart Car

```bash
uv run smart-car forward --duration 1
uv run smart-car backward --duration 1
uv run smart-car left --duration 0.5
uv run smart-car right --duration 0.5
uv run smart-car stop
```

### Assistant vocal / runtime

```bash
uv run voice-runtime
uv run voice-runtime --input-device bluetooth
```

En écoute continue sur le Pi, dire : **« cherche la balle jaune, approche-toi à 1 m puis suis-la pendant 5 min »**. Le runtime valide et borne un plan `search_and_approach_object` puis `follow_object`, avec cible `yellow`, `stand_off_cm=100` et `duration_s=300`. Le LLM ne pilote jamais le matériel : `Intent` -> validation/bornage -> skills -> `RobotController`.

Paramètres objet :
- `stand_off_cm` : distance de consigne (défaut 100 cm), bornée par `[limits] min_stand_off_cm` / `max_stand_off_cm` (30–300 cm) ;
- `duration_s` : durée du suivi (défaut 60 s), recherche comprise, bornée à 1–`max_follow_duration_sec` (600 s) ;
- `search_timeout_s` : budget de recherche, borné à 1–120 s ; défaut `[runtime] search_timeout_seconds` (25 s).

`[runtime] timeout_margin_seconds` (10 s) ajoute une marge au budget d'une étape avec `duration_s` ; le budget mission tient compte des étapes. Pendant une mission en écoute continue, **« stop »** déclenche immédiatement l'arrêt d'urgence ; les autres commandes ne lancent pas de mission concurrente. Ctrl+C arrête aussi le robot. Une urgence ou un obstacle interrompt le plan (`aborted`), sans retry ni étape suivante ; arrêt moteur garanti en sortie. Le suivi peut reculer : **aucun capteur arrière**, garder une zone dégagée.

Validation Mac sans matériel :

```bash
bash scripts/test/run_runtime_standard_scenarios_mac.sh
uv run pytest -q tests/unit/test_scenario_yellow_ball.py
```

Le scénario « balle jaune » du script utilise une perception mock et un `FakeRobot` avec horloge virtuelle : 300 s simulées sans attendre cinq minutes, sans LLM pour ce cas. Les quatre autres scénarios utilisent le serveur LLM local. Statuts et traces sont consignés dans `target/logs/scenario_runs/`.

### Tests Python

```bash
uv run pytest -q tests/unit tests/integration
```

Sur Mac, `uv run pytest -q` sans sélection tente aussi de collecter les scripts de `tests/hardware/` et échoue si `gpiozero` est absent. Ces scripts sont à exécuter sur le Pi avec le matériel adapté.

## Concepts clés

- `Intent` : intention structurée issue d'une commande naturelle
- `Skill` : action atomique ou logique de haut niveau
- `SkillPlanner` : mapping `Intent` -> plan de skills
- `SkillExecutor` : exécution du plan
- `RobotController` : adaptation au matériel réel

## Matériel supporté

Le dépôt couvre plusieurs axes de test :
- caméra CSI
- capteurs / distance / GPIO
- LED / audio / microphones
- Smart Car 2WD avec L298N
- assistant vocal local hors ligne

## Documentation

- `docs/guide-installation-llm-mac-portable.md` : installation portable du LLM sur Mac
- `docs/guide-installation-llm-local-pi5.md` : installation locale sur Raspberry Pi
- `PROJECT_CONTEXT.md` : contexte technique et règles de structure du dépôt
- `scripts/README.md` : vue d'ensemble des scripts d'installation et de test

## Règles de structure

Le dépôt suit une séparation claire entre :
- `scripts/install/` : installation système / matériel / LLM / Bluetooth
- `scripts/test/` : validation locale / runtime / démonstration
- `tests/` : tests Python automatisés

Cette séparation permet de ne pas mélanger :
- configuration système
- validation fonctionnelle locale
- tests de qualité automatisés

## Dépannage rapide

- `cmake` manquant sur macOS : installer les Xcode Command Line Tools puis `cmake`
- serveur LLM non dispo : `bash scripts/test/run_llm_runtime_mac.sh`
- `uv` absent : installer `uv` puis relancer `uv sync --project .`

## Licence et usage

Ce dépôt est un environnement de prototypage / laboratoire. Il sert à valider les composants matériels et la logique de commande robotique, pas à fournir un produit finalisé.