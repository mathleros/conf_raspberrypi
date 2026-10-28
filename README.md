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

- Raspberry Pi 4 ou 5
- Raspberry Pi OS 64 bits
- Python >= 3.12
- `uv` pour la gestion du projet
- outils système selon le matériel utilisé

## Démarrage rapide

### 1. Installer les dépendances Python

```bash
cd /path/to/conf_raspberrypi
uv sync --project .
```

### 2. Installer le LLM local sur macOS (portable)

```bash
cd /path/to/conf_raspberrypi
bash scripts/install/install_llm_mac_portable.sh
```

### 3. Tester le runtime sans microphone sur Mac

```bash
cd /path/to/conf_raspberrypi
bash scripts/test/run_llm_runtime_mac.sh --text "va vers la balle rouge"
```

### 4. Lancer un test de runtime complet

```bash
bash scripts/test/run_llm_runtime_mac.sh
```

### 5. Tester le runtime LLM local sur Mac sans microphone

Pour valider la logique end-to-end avec le LLM local en envoyant directement un texte de commande :

```bash
cd /Users/mathieu/Documents/Mathieu/Development/iRobotCacib/conf_raspberrypi
bash scripts/test/run_llm_runtime_mac.sh --text "va vers la balle rouge"
```

Version plus complète, qui lance le serveur puis exécute plusieurs validations :

```bash
cd /Users/mathieu/Documents/Mathieu/Development/iRobotCacib/conf_raspberrypi
bash scripts/test/run_llm_runtime_mac.sh
```

Cette commande est le point d'entrée recommandé pour vérifier que le pipeline texte -> `Intent` -> skills fonctionne bien sur un Mac sans micro.

### 6. LLM local sur Raspberry Pi 5 (Qwen2.5-1.5B-Instruct)

Modèle : **Qwen2.5-1.5B-Instruct**, GGUF quantisé **Q4_K_M** (~1,1 GB), servi par `llama-server` (`--ctx-size 2048`, alias `qwen2.5-1.5b`) sur `127.0.0.1:8080`.

```bash
sudo ./scripts/install/install_llm.sh
sudo systemctl start llm.service
curl http://127.0.0.1:8080/v1/models
uv run voice-runtime
```

Fonctionnement du runtime (`voice_runtime.py`) :
- la transcription est d'abord normalisée de façon déterministe (`text_normalizer.preprocess` : nombres en lettres -> chiffres, minutes -> secondes, mètres -> centimètres) ;
- prompt système court et statique, appel non streamé avec `response_format: json_object` (nouvel essai sans si le serveur répond HTTP 400) et `cache_prompt` ; préchauffage du cache au démarrage ;
- timeout, erreur HTTP, JSON invalide ou clé `steps` absente -> repli sur le parseur local ; `{"steps": []}` -> commande rejetée (`unsupported command`), aucun mouvement.

Variables d'environnement (défauts) : `LLM_MODEL` (`qwen2.5-1.5b`), `LLM_CONNECT_TIMEOUT_SECONDS` (1.0), `LLM_READ_TIMEOUT_SECONDS` (4.0), `LLM_MAX_TOKENS_PLAN` (160), `LLM_MAX_TOKENS_INTENT` (96).

Évaluation du prompt sur le serveur : `python3 scripts/test/eval_prompt_plan.py --repeat 3`.

## Commandes utiles

### Caméra

```bash
uv run camera-live
uv run color-detector
```

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
uv run voice-assistant --once
uv run voice-assistant --once --input-device bluetooth
```

### Tests Python

```bash
pytest
```

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