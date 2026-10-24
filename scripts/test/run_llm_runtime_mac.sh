#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_ROOT}"

LLAMA_BINARY="${PROJECT_ROOT}/target/llama.cpp/build/bin/llama-server"
MODEL_PATH="${PROJECT_ROOT}/target/models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
LLM_URL="http://127.0.0.1:8080/v1/models"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: $0 [--text 'phrase'] [--mock-object-position 'centre']"
    echo ""
    echo "Démarre le serveur LLM portable local puis exécute le runtime sur Mac."
    echo "Aucun microphone n'est utilisé."
    echo "Exemples :"
    echo "  bash $0"
    echo "  bash $0 --text 'va vers la balle rouge'"
    echo "  bash $0 --text 'cherche un objet puis approche toi' --mock-object-position 'centre'"
    exit 0
fi

TEXT=""
MOCK_OBJECT_POSITION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --text)
            shift
            TEXT="${1:-}"
            ;;
        --mock-object-position)
            shift
            MOCK_OBJECT_POSITION="${1:-}"
            ;;
        *)
            echo "Argument inconnu: $1"
            echo "Utilise --help pour voir les options."
            exit 1
            ;;
    esac
    shift || true
done

if [[ -z "${TEXT}" ]]; then
    if [[ -t 0 ]]; then
        echo "Saisis le texte à analyser par le runtime LLM."
        read -r -p "Texte: " TEXT
    else
        TEXT="$(cat)"
    fi
fi

if [[ -z "${TEXT}" ]]; then
    echo "Aucun texte fourni."
    echo "Utilise : bash $0 --text 'va vers la balle rouge'"
    exit 1
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
PYTHONPATH=src uv run python - "$TEXT" "$MOCK_OBJECT_POSITION" <<'PY'
import sys
from irobot.domain.skills.base_skill import SkillResult
from irobot.domain.skills.perception.detect_object import DetectObjectSkill
from irobot.interfaces.voice_runtime import VoiceRuntime
from tests.unit.fake_robot import FakeRobot

text = sys.argv[1]
mock_object_position = sys.argv[2] if len(sys.argv) > 2 else ""

if mock_object_position:
    def mocked_detect_execute(self, context):
        context.state["last_object_position"] = mock_object_position
        return SkillResult(
            status="success",
            message=f"[MOCK] Objet détecté ({mock_object_position}).",
            data={"position": mock_object_position, "target_object": "object"},
            confidence=1.0,
            next_action="align_to_target",
        )

    DetectObjectSkill.execute = mocked_detect_execute

runtime = VoiceRuntime(robot=FakeRobot(), use_llm=True)
print(f"\nTexte saisi : {text}")
if mock_object_position:
    print(f"Mode mock objet actif: position={mock_object_position}")
result = runtime.handle_text_as_plan(text)
print(result)
if isinstance(result, dict) and result.get("trace_path"):
    print(f"TRACE_PATH={result['trace_path']}")
PY
