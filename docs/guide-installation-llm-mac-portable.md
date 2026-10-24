# Installation portable du LLM pour macOS

Ce guide décrit la méthode recommandée pour installer le moteur LLM local du projet sur un Mac sans dépendre d'une installation système globale ni de Homebrew.

Le but est de conserver toute la stack du LLM dans le dossier `target/` du projet `conf_raspberrypi`.

## Objectif

Le projet consomme un serveur local compatible OpenAI sur cette URL :

```text
http://127.0.0.1:8080/v1/chat/completions
```

La méthode portable consiste à :
- installer `llama.cpp` dans `target/llama.cpp`
- télécharger le modèle GGUF dans `target/models/`
- lancer `llama-server` depuis ce dossier local

## Script à utiliser

```bash
scripts/install/install_llm_mac_portable.sh
```

Ce script crée automatiquement :
- `target/llama.cpp`
- `target/models/`
- `target/models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf`

## Prérequis

Vérifie simplement que ces outils sont disponibles :

```bash
xcode-select -p
clang --version
cmake --version
```

Si un élément manque, installe d'abord les Xcode Command Line Tools puis `cmake`.

## Installation

Depuis la racine du projet :

```bash
cd /Users/mathieu/Documents/Mathieu/Development/iRobotCacib/conf_raspberrypi
bash scripts/install/install_llm_mac_portable.sh
```

Le script va alors :
1. vérifier les dépendances système
2. préparer `target/`
3. cloner `llama.cpp`
4. compiler `llama-server`
5. télécharger le modèle GGUF

## Démarrer le serveur

```bash
bash scripts/install/install_llm_mac_portable.sh --start
```

Ou démarrage manuel :

```bash
cd /Users/mathieu/Documents/Mathieu/Development/iRobotCacib/conf_raspberrypi
"$PWD/target/llama.cpp/build/bin/llama-server" \
  -m "$PWD/target/models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf" \
  --host 127.0.0.1 \
  --port 8080 \
  --ctx-size 4096 \
  --threads 4 \
  --parallel 1
```

## Vérification

Dans un autre terminal :

```bash
curl http://127.0.0.1:8080/v1/models
```

## Test du runtime sans microphone

```bash
cd /Users/mathieu/Documents/Mathieu/Development/iRobotCacib/conf_raspberrypi
PYTHONPATH=src uv run python - <<'PY'
from irobot.interfaces.voice_runtime import VoiceRuntime
from tests.unit.fake_robot import FakeRobot

runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True)
for text in [
    "va vers la balle rouge",
    "stop maintenant",
    "tourne à gauche",
    "avance",
]:
    print(f"\n--- texte: {text}")
    print(runtime.handle_text(text))
PY
```

## Structure finale

```text
conf_raspberrypi/
├── target/
│   ├── llama.cpp/
│   │   └── build/
│   └── models/
│       └── Ministral-3-3B-Instruct-2512-Q4_K_M.gguf
├── scripts/
│   ├── install/
│   │   └── install_llm_mac_portable.sh
│   └── test/
│       └── run_llm_runtime_mac.sh
└── src/
```

## Points importants

- pas de `sudo`
- pas de service système
- compatible avec le projet sans dépendre de `brew`
- compatible macOS Intel et Apple Silicon
- installation entièrement contenue dans `target/`

## Résumé

La méthode portable sans Homebrew est la voie retenue pour le développement sur Mac, notamment sur un Intel où Homebrew n’est pas fiable ni supporté de façon stable.
