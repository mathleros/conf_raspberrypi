#!/usr/bin/env bash
#
# Installation de l'assistant vocal local :
#   - llama.cpp (compile pour ARM) + llama-server (API OpenAI-compatible)
#   - modèle Ministral 3 3B Instruct (le plus petit LLM de chez Mistral)
#   - package Python vosk (STT français) + modèle vosk-model-small-fr
#
# Usage :
#   sudo ./install_llm.sh

set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Ce script doit être exécuté avec sudo :"
    echo "    sudo ./install_llm.sh"
    exit 1
fi

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
MODEL_URL="https://huggingface.co/unsloth/Ministral-3-3B-Instruct-2512-GGUF/resolve/main/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
MODEL_FILE="${MODELS_DIR}/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"

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
cmake -S "${LLAMA_DIR}" -B "${LLAMA_DIR}/build" -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=ON
cmake --build "${LLAMA_DIR}/build" -j"$(nproc)" --target llama-server

cat > /usr/local/bin/ministral-server <<SHELL
#!/usr/bin/env bash
exec ${LLAMA_DIR}/build/bin/llama-server \
    -m ${MODEL_FILE} \
    --host 127.0.0.1 --port 8080 \
    --ctx-size 2048 --threads 4 --parallel 1
SHELL
chmod +x /usr/local/bin/ministral-server

echo "── 3/6 Téléchargement du modèle Ministral 3 3B ──"
mkdir -p "${MODELS_DIR}"
if [[ ! -f "${MODEL_FILE}" ]]; then
    echo "Téléchargement (~2,2 GB)…"
    curl -L --progress-bar -o "${MODEL_FILE}" "${MODEL_URL}"
else
    echo "Modèle déjà présent."
fi

echo "── 4/6 Service systemd ministral ──"
cat > /etc/systemd/system/ministral.service <<'SHELL'
[Unit]
Description=llama-server Ministral 3 3B (LLM local, API :8080)
After=network.target

[Service]
ExecStart=/usr/local/bin/ministral-server
Restart=on-failure
User=${TARGET_USER}

[Install]
WantedBy=multi-user.target
SHELL
systemctl daemon-reload
systemctl enable ministral.service

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
echo "  Démarre le serveur LLM :  sudo systemctl start ministral.service"
echo "  Test de l'API :            curl http://127.0.0.1:8080/v1/models"
echo "  Assistant vocal :          cd '${PROJECT_DIR}' && uv run voice-assistant"