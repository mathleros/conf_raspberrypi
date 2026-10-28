#!/usr/bin/env bash
#
# Installation de l'assistant vocal local :
#   - llama.cpp (compile pour ARM) + llama-server (API OpenAI-compatible)
#   - modèle LLM : Qwen2.5-1.5B-Instruct (GGUF Q4_K_M, ~1,1 GB)
#   - package Python vosk (STT français) + modèle vosk-model-small-fr
#
# Usage :
#   sudo ./install_llm.sh
#   sudo MODEL_URL=... MODEL_FILENAME=... ./install_llm.sh   # autre fichier GGUF (optionnel)

set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Ce script doit être exécuté avec sudo :"
    echo "    sudo ./install_llm.sh"
    exit 1
fi

if [[ $# -gt 0 ]]; then
    echo "Option inconnue : $1 (usage : sudo ./install_llm.sh)"
    exit 1
fi

# Nom exposé par llama-server (--alias) ; le runtime l'envoie via la variable LLM_MODEL.
LLM_MODEL="${LLM_MODEL:-qwen2.5-1.5b}"
MODEL_LABEL="Qwen2.5-1.5B-Instruct (GGUF Q4_K_M)"
MODEL_SIZE="~1,1 GB"
MODEL_FILENAME="${MODEL_FILENAME:-qwen2.5-1.5b-instruct-q4_k_m.gguf}"
MODEL_URL="${MODEL_URL:-https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/${MODEL_FILENAME}}"

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

# Racine du dépôt (le script est dans scripts/install/) : c'est là que se trouve pyproject.toml.
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ ! -f "${PROJECT_DIR}/pyproject.toml" ]]; then
    echo "Erreur : pyproject.toml introuvable dans ${PROJECT_DIR}."
    exit 1
fi
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
    --alias ${LLM_MODEL} \
    --host 127.0.0.1 --port 8080 \
    --ctx-size 2048 --threads 4 --parallel 1
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
echo "  Commande vocale :          cd '${PROJECT_DIR}' && uv run voice-runtime"