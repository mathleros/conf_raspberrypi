#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${PROJECT_ROOT}/target"
LLAMA_DIR="${TARGET_DIR}/llama.cpp"
MODELS_DIR="${TARGET_DIR}/models"
MODEL_NAME="Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
MODEL_PATH="${MODELS_DIR}/${MODEL_NAME}"
MODEL_URL="https://huggingface.co/unsloth/Ministral-3-3B-Instruct-2512-GGUF/resolve/main/${MODEL_NAME}"
START_SERVER=false

if [[ "${1:-}" == "--start" ]]; then
    START_SERVER=true
fi

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: $0 [--start]"
    echo ""
    echo "Installe un LLM portable sans Homebrew sur macOS Intel."
    echo "Le binaire et le modèle sont installés dans le dossier target/ du projet."
    echo "Avec --start, le serveur LLM est lancé immédiatement après l'installation."
    exit 0
fi

echo "[1/4] Vérification des outils système"
if ! xcode-select -p >/dev/null 2>&1; then
    echo "Les Xcode Command Line Tools ne sont pas installés."
    echo "Lancez : xcode-select --install"
    exit 1
fi

if ! command -v clang >/dev/null 2>&1; then
    echo "clang n'est pas disponible."
    echo "Installez les Xcode Command Line Tools : xcode-select --install"
    exit 1
fi

if ! command -v git >/dev/null 2>&1; then
    echo "git est absent. Installez les Xcode Command Line Tools : xcode-select --install"
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "curl est absent. Installez les Xcode Command Line Tools : xcode-select --install"
    exit 1
fi

if ! command -v cmake >/dev/null 2>&1; then
    CMAKE_APP="/Applications/CMake.app/Contents/bin/cmake"
    if [[ -x "${CMAKE_APP}" ]]; then
        export PATH="$(dirname "${CMAKE_APP}"):${PATH}"
    else
        echo "cmake est absent."
        echo "Téléchargez-le depuis : https://cmake.org/download/"
        echo "puis relancez ce script."
        exit 1
    fi
fi

echo "[2/4] Préparation du dossier portable"
mkdir -p "${TARGET_DIR}" "${MODELS_DIR}"

echo "[3/4] Téléchargement / compilation de llama.cpp"
if [[ ! -d "${LLAMA_DIR}" ]]; then
    git clone --depth 1 https://github.com/ggml-org/llama.cpp "${LLAMA_DIR}"
else
    git -C "${LLAMA_DIR}" pull --ff-only || true
fi

cmake -S "${LLAMA_DIR}" -B "${LLAMA_DIR}/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "${LLAMA_DIR}/build" --config Release -j"$(sysctl -n hw.ncpu)"

echo "[4/4] Téléchargement du modèle GGUF"
if [[ ! -f "${MODEL_PATH}" ]]; then
    curl -L --fail --progress-bar -o "${MODEL_PATH}" "${MODEL_URL}"
else
    echo "Le modèle est déjà présent : ${MODEL_PATH}"
fi

echo ""
echo "Installation portable terminée."
echo "Dossier cible : ${TARGET_DIR}"
echo "Binaire : ${LLAMA_DIR}/build/bin/llama-server"
echo "Modèle : ${MODEL_PATH}"
echo ""
echo "Pour lancer le serveur LLM :"
echo "  \"${LLAMA_DIR}/build/bin/llama-server\" -m \"${MODEL_PATH}\" --host 127.0.0.1 --port 8080 --ctx-size 4096 --threads 4 --parallel 1"
echo ""
echo "Pour tester l'API :"
echo "  curl http://127.0.0.1:8080/v1/models"
echo ""
echo "Pour lancer immédiatement le serveur avec ce script :"
echo "  bash ${0} --start"

if [[ "${START_SERVER}" == true ]]; then
    echo ""
    echo "Démarrage du serveur LLM portable..."
    exec "${LLAMA_DIR}/build/bin/llama-server" \
        -m "${MODEL_PATH}" \
        --host 127.0.0.1 \
        --port 8080 \
        --ctx-size 4096 \
        --threads 4 \
        --parallel 1
fi
