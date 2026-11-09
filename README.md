# Raspberry Pi / iRobot playground

Ce dépôt est un banc d'essai robotique autour d'un Raspberry Pi : caméra, audio, capteurs, Smart Car 2WD, assistant vocal local et orchestration de skills.

Le projet a évolué vers une architecture plus claire :
- l'entrée texte / voix est transformée en `Intent`
- l'`Intent` est validée puis convertie en plan de `Skill`s
- le plan est exécuté par un orchestrateur
- le matériel n'est jamais piloté directement par le LLM, mais via des skills et un adaptateur robot

## Architecture actuelle

```text
Micro → Vosk →┐
              ├→ CommandService → plan LLM / TextIntentParser
Texte direct ─┘                         ↓
                                Intent validés
  ↓
SkillPlanner → SkillPlanStep(intent + skills) / SkillRegistry
  ↓
MissionOrchestrator → LanguageController → SkillExecutor
  ↓
Skills → RobotController → adaptateurs matériels
```

`VoiceRuntime` gère l'écoute et les arrêts vocaux immédiats. Les commandes texte
et transcrites convergent vers `CommandService`. `SkillPlanner` compile les
intents en étapes ; `MissionOrchestrator` pilote leur séquence, les retries,
les délais et l'état de mission. `LanguageController` exécute les étapes
compilées ; il ne parse pas de texte.

Les modules sont organisés par responsabilité : `src/irobot/app/` (code partagé :
`domain/`, `interfaces/`, `hardware/`, `config/`, `tools/`), `src/irobot/app/` (runtime
vocal LLM) et `src/irobot/tools/robot_test/` (banc de test direct `robot-test`, sans LLM).
Le [README du package](src/irobot/README.md) décrit les points d'entrée et
les limites actuelles du runtime.

Le suivi de « moi » utilise une cible visuelle ArUco (`follow_person`) ; il ne
s'agit pas d'une reconnaissance d'identité. Le LLM propose un plan, mais ne
commande jamais directement les moteurs ou les GPIO.

## Structure du dépôt

```text
.
├── README.md
├── PROJECT_CONTEXT.md
├── pyproject.toml
├── uv.lock
├── assets/
│   ├── aruco/
│   └── vision/
├── docs/
│   ├── guide-installation-llm-local-pi5.md
│   ├── guide-installation-llm-mac-portable.md
│   └── test-campaign/
├── scripts/
│   ├── README.md
│   ├── install/
│   ├── scenarios/
│   └── ssh_connect.sh
├── specs/
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
- Connexion réseau et espace disque suffisant pour compiler llama.cpp et télécharger les modèles (prévoir au moins 6 Go)
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

Pour vérifier la vision sur le Pi avec affichage X11, lancer
`uv run vision-detect-live` : ID ArUco 1, visage et balles rouge/jaune sont
détectés simultanément, avec distances estimées et rectangles/coins.
L'outil [vision_diagnostic.py](src/irobot/tools/vision_diagnostic.py) réutilise
la correction du contre-jour et les détecteurs du runtime, sans moteur ni
enregistrement. Quitter avec `q` ou Ctrl+C. Voir les [réglages et limites](src/irobot/README.md#diagnostic-vision).

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

Le service est activé au démarrage par l'installateur. Pour essayer l'assistant vocal sur le Pi une fois le microphone configuré, lancer `uv run robot` depuis la racine du projet (Ctrl+C pour quitter).

### 6. Configurer le matériel et les paramètres du runtime

Choisir et installer **une** configuration micro selon le matériel :

```bash
# Casque Bluetooth (optionnel)
sudo ./scripts/install/install_bluetooth_audio.sh
sudo reboot
./scripts/install/connect_jabra_bt.sh scan
./scripts/install/connect_jabra_bt.sh <ADRESSE_MAC_DU_CASQUE>
bluetoothctl info <ADRESSE_MAC_DU_CASQUE>
uv run robot --once --input-device bluetooth
```

Pour le HAT **ReSpeaker 2-Mic** à la place du casque Bluetooth :

```bash
sudo ./scripts/install/install_respeaker.sh
sudo reboot
aplay -l
arecord -l
uv run robot --once --input-device wm8960
```

Le ReSpeaker requiert le HAT connecté avant le redémarrage pour charger son overlay audio. Les scripts Bluetooth et ReSpeaker ne sont pas nécessaires pour le runtime texte/LLM.

Les paramètres du robot et de la perception sont dans [runtime_settings.toml](src/irobot/app/config/runtime_settings.toml), à côté du module qui les charge. Après installation et branchement de la caméra, calibrer si nécessaire la focale avec `uv run calibrate-distance --known-distance-cm 100`, puis reporter la valeur `focal_px` affichée dans la section `[camera]` du fichier.

Le raccordement logiciel SH-04 utilise la section `[human_follow]` du même
fichier : `max_age_seconds = 0.2` et `announcement_timeout_seconds = 2.0`.
Ces défauts provisoires sont autorisés, **pas qualifiés**. Les appels structurés
sans surcharge prennent ces budgets depuis les réglages du runtime ; une
surcharge explicite de replay reste prioritaire. Les budgets sont figés pendant
la mission, reprise comprise ; une modification exige une nouvelle mission
avec des réglages rechargés. Valeur non numérique, non finie ou non positive,
table malformée ou clé inconnue : erreur explicite, aucun repli silencieux.
Ces valeurs ne qualifient pas le suivi humain sur matériel réel. La
[campagne de tests sur Raspberry Pi](docs/test-campaign/test_plan.md) rappelle
les précautions et preuves nécessaires avant toute validation matérielle.

**Sécurité matériel :** avant tout essai susceptible de commander les moteurs, placer le robot sur un support stable avec les roues dégagées, puis vérifier l'arrêt d'urgence et le câblage.

### Installation et tests sur macOS

Pour installer le LLM portable sur Mac et tester le pipeline sans microphone ni
matériel robot :

```bash
cd /path/to/conf_raspberrypi
bash scripts/install/install_llm_mac_portable.sh
bash scripts/scenarios/run_llm_runtime_mac.sh --text "va vers la balle rouge"
```

L'installateur prend en charge `qwen2.5-1.5b` (par défaut) et
`ministral-3-3b`. Pour choisir le modèle :

```bash
bash scripts/install/install_llm_mac_portable.sh --model ministral-3-3b
LLM_MODEL=ministral-3-3b bash scripts/scenarios/run_llm_runtime_mac.sh --text "va vers la balle rouge"
```

Le script `run_llm_runtime_mac.sh` démarre le serveur local si nécessaire et
exécute le runtime en mode texte ; sans `--text`, il demande une phrase au
terminal. Il n'utilise ni microphone ni matériel robot.

### LLM et runtime sur Raspberry Pi

Le Pi sert **Qwen2.5-1.5B-Instruct** quantisé **Q4_K_M** (~1,1 Go) via `llama-server`, sur `127.0.0.1:8080` (alias `qwen2.5-1.5b`, contexte 2048). Pour les étapes d'installation manuelle, les réglages de performance ou le dépannage avancé, voir [docs/guide-installation-llm-local-pi5.md](docs/guide-installation-llm-local-pi5.md).

Fonctionnement du runtime (`voice_runtime.py`) :
- la transcription est normalisée de façon déterministe (nombres en lettres -> chiffres, minutes -> secondes, mètres -> centimètres) ;
- les commandes d'arrêt (« stop », « arrête toi », « halte », « pause ») sont traitées localement, sans LLM ;
- le prompt de planification explique que « moi » désigne le marqueur : « approche-toi de moi » produit `search_and_approach_object` avec `target="marker"`, tandis que « suis-moi » produit `follow_person`, un suivi continu de ce marqueur jusqu'à l'arrêt ;
- le LLM interprète les commandes et leurs plans composés ; le parseur local reste disponible sans LLM ou en repli technique ;
- le plan LLM est contrôlé lexicalement ; toute intention ou valeur numérique non justifiée par la phrase est rejetée ;
- en cas de timeout, d'erreur HTTP, de JSON invalide ou de réponse incomplète, le parseur local prend le relais ; une liste d'étapes vide est rejetée.

Variables d'environnement principales : `LLM_MODEL` (`qwen2.5-1.5b`),
`LLM_CONNECT_TIMEOUT_SECONDS` (1), `LLM_READ_TIMEOUT_SECONDS` (10),
`LLM_MAX_TOKENS_PLAN` (120), `LLM_RESPONSE_FORMAT` (`schema`,
`json_object` ou `none`) et `LLM_WARMUP_WAIT_SECONDS` (60). Les traces
JSONL détaillent notamment la latence, le format de réponse, les tentatives,
les tokens et les erreurs LLM. Pour évaluer le prompt contre le serveur local :

```bash
uv run python scripts/scenarios/eval_prompt_plan.py --repeat 3
```

Pour vérifier que le LLM retourne `target="marker"` pour « moi », sans commander les moteurs :

```bash
uv run python scripts/scenarios/eval_prompt_plan.py --only approche_moi,approche_moi_plan,suis_moi --schema --repeat 3
```

## Commandes utiles

### Caméra

```bash
uv run vision-detect-live --preview-only
uv run vision-detect-live
# Sur Pi : balle jaune centrée à 100 cm mesurés depuis la caméra
uv run calibrate-distance --color yellow --ball-diameter-cm 6.5 --known-distance-cm 100
# Après avoir reporté focal_px dans [camera], vérifier l'estimation en direct
uv run calibrate-distance --color yellow
```

`calibrate-distance` prend 30 mesures par défaut (`--samples` pour changer ce nombre) et affiche la focale à reporter manuellement dans [runtime_settings.toml](src/irobot/app/config/runtime_settings.toml). Renseigner aussi le diamètre réel `ball_diameter_cm` dans ce fichier. La distance visuelle est estimée par `focal_px * ball_diameter_cm / diameter_px`, puis lissée dans la perception live. L'ultrason reste réservé aux mesures d'obstacles du robot et n'est pas utilisé pour estimer la distance de la cible visuelle.

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
uv run robot
uv run robot --input-device bluetooth
```

En écoute continue sur le Pi, dire : **« cherche la balle jaune, approche-toi à 1 m puis suis-la pendant 5 min »**. Le runtime valide et borne un plan `search_and_approach_object` puis `follow_object`, avec cible `yellow`, `stand_off_cm=100` et `duration_s=300`. Le LLM ne pilote jamais le matériel : `Intent` -> validation/bornage -> skills -> `RobotController`.

Paramètres objet :
- `stand_off_cm` : distance de consigne (défaut 100 cm), bornée par `[limits] min_stand_off_cm` / `max_stand_off_cm` (30–300 cm) ;
- `duration_s` : durée optionnelle du suivi, bornée à 1–`max_follow_duration_sec` (600 s). Sans durée explicite, le suivi est continu jusqu'à une commande d'arrêt ;
- `search_timeout_s` : budget de recherche, borné à 1–120 s ; défaut `[runtime] search_timeout_seconds` (25 s).

Pour `follow_person`, la cible est le marqueur ArUco et la distance de consigne
par défaut est 20 cm ; aucune identification de personne n'est effectuée.
`[runtime] timeout_margin_seconds` (10 s) ajoute une marge au budget d'une
étape temporisée ; le budget de mission tient compte des étapes. Pendant une
mission en écoute continue, **« stop »** déclenche l'arrêt d'urgence ; les
autres commandes ne lancent pas de mission concurrente. Ctrl+C arrête aussi
le robot. Une urgence ou un obstacle interrompt le plan (`aborted`), sans
nouvelle tentative ni étape suivante. Le suivi peut reculer : **aucun capteur
arrière**, garder une zone dégagée.

Validation Mac sans matériel :

```bash
bash scripts/scenarios/run_runtime_standard_scenarios_mac.sh
uv run pytest -q tests/unit/test_scenario_yellow_ball.py
```

Le scénario « balle jaune » utilise une perception simulée et un `FakeRobot`
avec horloge virtuelle : 300 s sont simulées sans attendre cinq minutes ni
appeler le LLM pour ce cas. Les quatre autres scénarios du script utilisent
le serveur LLM local. Statuts et traces sont consignés dans
`target/logs/scenario_runs/`. Ces validations simulées ne remplacent pas la
campagne sur le robot réel décrite dans
[docs/test-campaign/test_plan.md](docs/test-campaign/test_plan.md).

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

- [Campagne de tests bout en bout sur Raspberry Pi](docs/test-campaign/test_plan.md) : étapes de recette physique, règles de sécurité et critères de verdict.
- [Guide d'installation du LLM sur macOS](docs/guide-installation-llm-mac-portable.md)
- [Guide d'installation du LLM sur Raspberry Pi 5](docs/guide-installation-llm-local-pi5.md)
- [Architecture fonctionnelle et technique](specs/02_functional_technical_architecture.md)
- [Contexte technique du projet](PROJECT_CONTEXT.md)
- [Vue d'ensemble des scripts](scripts/README.md)
- [Structure du package irobot](src/irobot/README.md)
- [Configuration du runtime](src/irobot/app/config/README.md)

## Règles de structure

Le dépôt suit une séparation claire entre :
- `scripts/install/` : installation système / matériel / LLM / Bluetooth
- `scripts/scenarios/` : validation locale / runtime / démonstration
- `tests/` : tests Python automatisés

Cette séparation permet de ne pas mélanger :
- configuration système
- validation fonctionnelle locale
- tests de qualité automatisés

## Dépannage rapide

- `cmake` manquant sur macOS : installer les Xcode Command Line Tools puis `cmake`
- serveur LLM non dispo : `bash scripts/scenarios/run_llm_runtime_mac.sh`
- `uv` absent : installer `uv` puis relancer `uv sync --project .`

## Licence et usage

Ce dépôt est un environnement de prototypage / laboratoire. Il sert à valider les composants matériels et la logique de commande robotique, pas à fournir un produit finalisé.