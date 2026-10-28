#!/usr/bin/env bash
#
# Installation de l'assistant vocal local :
#   - llama.cpp (compile pour ARM) + llama-server (API OpenAI-compatible)
#   - modèle LLM au choix (défaut : qwen2.5-1.5b ; alternative : ministral-3-3b)
#   - package Python vosk (STT français) + modèle vosk-model-small-fr
#
# Usage :
#   sudo ./install_llm.sh [--model qwen2.5-1.5b|ministral-3-3b]
#   sudo LLM_MODEL=ministral-3-3b ./install_llm.sh

set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Ce script doit être exécuté avec sudo :"
    echo "    sudo ./install_llm.sh"
    exit 1
fi

LLM_MODEL="${LLM_MODEL:-qwen2.5-1.5b}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --model) LLM_MODEL="${2:?--model requiert une valeur}"; shift 2 ;;
        *) echo "Option inconnue : $1"; exit 1 ;;
    esac
done

case "${LLM_MODEL}" in
    qwen2.5-1.5b)
        MODEL_LABEL="Qwen 2.5 1.5B Instruct"
        MODEL_SIZE="~1,1 GB"
        MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
        MODEL_FILENAME="qwen2.5-1.5b-instruct-q4_k_m.gguf"
        ;;
    ministral-3-3b)
        MODEL_LABEL="Ministral 3 3B Instruct"
        MODEL_SIZE="~2,2 GB"
        MODEL_URL="https://huggingface.co/unsloth/Ministral-3-3B-Instruct-2512-GGUF/resolve/main/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
        MODEL_FILENAME="Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
        ;;
    *)
        echo "Modèle inconnu : ${LLM_MODEL} (valeurs : qwen2.5-1.5b, ministral-3-3b)"
        exit 1
        ;;
esac

TARGET_USER="${SUDO_USER:-}"
if [[ -z "${TARGET_USER}" || "${TARGET_USER}" == root ]]; then
    echo "Erreur : exécute ce script avec sudo depuis le compte utilisateur cible."
    exit 1
fi

TARGET_HOME=$(getent passwd "${TARGET_USER}" | cut -d: -f6)
if [[ -z "${TARGET_HOME}" || ! -d "${TARGET_HOME}" ]]; then
    echo "Erreur : impossible de trouver le dossier personnel de ${TARGET_USER}."
    exit 1
fi

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="${TARGET_HOME}/tools"
LLAMA_DIR="${TOOLS_DIR}/llama.cpp"
MODELS_DIR="${TARGET_HOME}/models"
MODEL_FILE="${MODELS_DIR}/${MODEL_FILENAME}"

echo "── 1/6 Dépendances système ──"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y cmake build-essential libcurl4-openssl-dev nlohmann-json3-dev

echo "── 2/6 Compilation llama.cpp ──"
mkdir -p "${TOOLS_DIR}"
if [[ ! -d "${LLAMA_DIR}" ]]; then
    git clone --depth 1 https://github.com/ggml-org/llama.cpp "${LLAMA_DIR}"
else
    git -C "${LLAMA_DIR}" pull --ff-only || true
fi
CMAKE_CACHE="${LLAMA_DIR}/build/CMakeCache.txt"
if [[ -f "${CMAKE_CACHE}" ]] && ! grep -q "^CMAKE_HOME_DIRECTORY:INTERNAL=${LLAMA_DIR}$" "${CMAKE_CACHE}"; then
    echo "Cache CMake issu d'un autre emplacement : reconstruction."
    rm -rf "${LLAMA_DIR}/build"
fi
cmake -S "${LLAMA_DIR}" -B "${LLAMA_DIR}/build" -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=ON
cmake --build "${LLAMA_DIR}/build" -j"$(nproc)" --target llama-server

cat > /usr/local/bin/llm-server <<SHELL
#!/usr/bin/env bash
exec ${LLAMA_DIR}/build/bin/llama-server \
    -m ${MODEL_FILE} \
    --host 127.0.0.1 --port 8080 \
    --ctx-size 1024 --threads 4 --parallel 1
SHELL
chmod +x /usr/local/bin/llm-server

echo "── 3/6 Téléchargement du modèle ${MODEL_LABEL} ──"
mkdir -p "${MODELS_DIR}"
if [[ ! -f "${MODEL_FILE}" ]]; then
    echo "Téléchargement (${MODEL_SIZE})…"
    curl -L --progress-bar -o "${MODEL_FILE}" "${MODEL_URL}"
else
    echo "Modèle déjà présent."
fi

echo "── 4/6 Service systemd llm ──"
cat > /etc/systemd/system/llm.service <<SHELL
[Unit]
Description=llama-server ${MODEL_LABEL} (LLM local, API :8080)
After=network.target

[Service]
ExecStart=/usr/local/bin/llm-server
Restart=on-failure
User=${TARGET_USER}

[Install]
WantedBy=multi-user.target
SHELL
systemctl daemon-reload
systemctl enable llm.service

echo "── 5/6 Paquets Python (vosk, request) ──"
su - "${TARGET_USER}" -c "uv sync --project '${PROJECT_DIR}'"

echo "── 6/6 Modèle Vosk français ──"
VOSK_MODEL_DIR="${MODELS_DIR}/vosk-model-small-fr-0.22"
if [[ ! -d "${VOSK_MODEL_DIR}" ]]; then
    echo "Téléchargement du modèle STT français (~45 MB)…"
    curl -L --progress-bar -o /tmp/vosk-fr.zip \
        "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip"
    apt-get install -y unzip
    unzip -qo /tmp/vosk-fr.zip -d "${MODELS_DIR}"
    rm -f /tmp/vosk-fr.zip
else
    echo "Modèle Vosk déjà présent."
fi

echo ""
echo "Installation terminée."
echo "  Démarre le serveur LLM :  sudo systemctl start llm.service"
echo "  Test de l'API :            curl http://127.0.0.1:8080/v1/models"
echo "  Assistant vocal :          cd '${PROJECT_DIR}' && uv run voice-assistant"