#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_ROOT}"

LLAMA_BINARY="${PROJECT_ROOT}/target/llama.cpp/build/bin/llama-server"
case "${LLM_MODEL:-qwen2.5-1.5b}" in
    qwen2.5-1.5b) MODEL_FILE="qwen2.5-1.5b-instruct-q4_k_m.gguf" ;;
    ministral-3-3b) MODEL_FILE="Ministral-3-3B-Instruct-2512-Q4_K_M.gguf" ;;
    *) echo "Modèle inconnu : ${LLM_MODEL}"; exit 1 ;;
esac
MODEL_PATH="${PROJECT_ROOT}/target/models/${MODEL_FILE}"
LLM_URL="http://127.0.0.1:8080/v1/models"
PID_FILE="/tmp/irobot_llama_runtime_mac.pid"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: $0 [--text 'phrase'] [--mock-object-position 'centre'] [--ctx-size TOKENS]"
    echo "       $0 --stop"
    echo ""
    echo "Démarre le serveur LLM portable local puis exécute le runtime sur Mac."
    echo "Aucun microphone n'est utilisé."
    echo "Exemples :"
    echo "  bash $0"
    echo "  bash $0 --text 'va vers la balle rouge'"
    echo "  bash $0 --ctx-size 8192 --text 'va vers la balle rouge'"
    echo "  bash $0 --stop"
    echo "  bash $0 --text 'cherche un objet puis approche toi' --mock-object-position 'centre'"
    exit 0
fi

TEXT=""
MOCK_OBJECT_POSITION=""
CTX_SIZE=4096
STOP_SERVER=0
OTHER_OPTION=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --stop)
            STOP_SERVER=1
            ;;
        --ctx-size)
            OTHER_OPTION=1
            if [[ $# -lt 2 ]]; then
                echo "Valeur manquante pour --ctx-size."
                exit 1
            fi
            shift
            CTX_SIZE="${1}"
            if [[ ! "${CTX_SIZE}" =~ ^[1-9][0-9]*$ ]]; then
                echo "La taille du contexte doit être un entier positif : ${CTX_SIZE}"
                exit 1
            fi
            ;;
        --text)
            OTHER_OPTION=1
            shift
            TEXT="${1:-}"
            ;;
        --mock-object-position)
            OTHER_OPTION=1
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

if [[ "${STOP_SERVER}" -eq 1 ]]; then
    if [[ "${OTHER_OPTION}" -eq 1 ]]; then
        echo "--stop ne peut pas être combiné avec les autres options."
        exit 1
    fi

    server_pids=()
    is_target_server() {
        local pid="$1"
        local command
        command="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
        [[ "${command}" == *"${LLAMA_BINARY}"* && "${command}" == *"--port 8080"* ]]
    }

    if [[ -f "${PID_FILE}" ]]; then
        saved_pid="$(<"${PID_FILE}")"
        if [[ "${saved_pid}" =~ ^[0-9]+$ ]] && kill -0 "${saved_pid}" 2>/dev/null; then
            if is_target_server "${saved_pid}"; then
                server_pids+=("${saved_pid}")
            else
                echo "Le PID enregistré n'est plus celui du serveur LLM; fichier PID ignoré."
            fi
        fi
        rm -f "${PID_FILE}"
    fi

    if command -v lsof >/dev/null 2>&1; then
        while IFS= read -r pid; do
            [[ "${pid}" =~ ^[0-9]+$ ]] || continue
            is_target_server "${pid}" || continue
            already_added=0
            for existing_pid in "${server_pids[@]}"; do
                if [[ "${existing_pid}" == "${pid}" ]]; then
                    already_added=1
                    break
                fi
            done
            if [[ "${already_added}" -eq 0 ]]; then
                server_pids+=("${pid}")
            fi
        done < <(lsof -nP -t -iTCP:8080 -sTCP:LISTEN 2>/dev/null || true)
    fi

    if [[ "${#server_pids[@]}" -eq 0 ]]; then
        echo "Aucun llama-server du projet n'est actif sur le port 8080."
        exit 0
    fi

    for pid in "${server_pids[@]}"; do
        kill -TERM "${pid}"
    done
    for pid in "${server_pids[@]}"; do
        for _ in $(seq 1 10); do
            if ! kill -0 "${pid}" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        if kill -0 "${pid}" 2>/dev/null; then
            echo "Le serveur (PID ${pid}) ne s'est pas arrêté après SIGTERM."
            exit 1
        fi
    done
    rm -f "${PID_FILE}"
    echo "Serveur LLM arrêté."
    exit 0
fi

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
        --ctx-size "${CTX_SIZE}" \
        --threads 4 \
        --parallel 1 > /tmp/irobot_llama.log 2>&1 &

    SERVER_PID=$!
    printf '%s\n' "${SERVER_PID}" > "${PID_FILE}"
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
