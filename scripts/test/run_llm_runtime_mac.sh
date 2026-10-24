#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

LLAMA_BINARY="${PROJECT_ROOT}/target/llama.cpp/build/bin/llama-server"
MODEL_PATH="${PROJECT_ROOT}/target/models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
LLM_URL="http://127.0.0.1:8080/v1/models"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: $0 [--text 'phrase']"
    echo ""
    echo "Démarre le serveur LLM portable local puis exécute le runtime sur Mac."
    echo "Aucun microphone n'est utilisé."
    echo "Exemples :"
    echo "  bash $0"
    echo "  bash $0 --text 'va vers la balle rouge'"
    exit 0
fi

TEXT=""
if [[ "${1:-}" == "--text" ]]; then
    shift
    TEXT="${1:-}"
fi

if [[ ! -x "${LLAMA_BINARY}" ]]; then
    echo "llama-server n'a pas été trouvé : ${LLAMA_BINARY}"
    echo "Je tente l'installation portable sans Homebrew..."
    bash scripts/install/install_llm_mac_portable.sh
fi

if [[ ! -f "${MODEL_PATH}" ]]; then
    echo "Modèle introuvable : ${MODEL_PATH}"
    echo "Je tente l'installation portable sans Homebrew..."
    bash scripts/install/install_llm_mac_portable.sh
fi

if ! curl -fsS "${LLM_URL}" >/dev/null 2>&1; then
    echo "Démarrage du serveur LLM local..."
    "${LLAMA_BINARY}" \
        -m "${MODEL_PATH}" \
        --host 127.0.0.1 \
        --port 8080 \
        --ctx-size 4096 \
        --threads 4 \
        --parallel 1 > /tmp/irobot_llama.log 2>&1 &

    SERVER_PID=$!
    echo "PID serveur : ${SERVER_PID}"

    for _ in $(seq 1 60); do
        if curl -fsS "${LLM_URL}" >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    if ! curl -fsS "${LLM_URL}" >/dev/null 2>&1; then
        echo "Le serveur LLM n'a pas démarré correctement."
        echo "Log : /tmp/irobot_llama.log"
        exit 1
    fi
fi

echo "Serveur LLM disponible sur http://127.0.0.1:8080"

echo ""
if [[ -n "${TEXT}" ]]; then
    PYTHONPATH=src uv run python - "$TEXT" <<'PY'
import sys
from irobot.interfaces.voice_runtime import VoiceRuntime
from tests.unit.fake_robot import FakeRobot

text = sys.argv[1]
runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True)
print(f"\n--- texte: {text}")
print(runtime.handle_text(text))
PY
else
    PYTHONPATH=src uv run python <<'PY'
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
fi
