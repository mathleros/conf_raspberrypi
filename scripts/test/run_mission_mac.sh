#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_ROOT}"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: $0 --text 'mission' [--mock-object-position centre] [--replay]"
    exit 0
fi

TEXT=""
MOCK_OBJECT_POSITION=""
REPLAY="false"

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
        --replay)
            REPLAY="true"
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
    shift || true
done

if [[ -z "${TEXT}" ]]; then
    echo "Missing --text"
    exit 1
fi

OUT="$(mktemp)"
if [[ -n "${MOCK_OBJECT_POSITION}" ]]; then
    bash scripts/test/run_llm_runtime_mac.sh --text "${TEXT}" --mock-object-position "${MOCK_OBJECT_POSITION}" | tee "${OUT}"
else
    bash scripts/test/run_llm_runtime_mac.sh --text "${TEXT}" | tee "${OUT}"
fi

TRACE_PATH="$(grep -E '^TRACE_PATH=' "${OUT}" | sed 's/^TRACE_PATH=//' || true)"
rm -f "${OUT}"

if [[ "${REPLAY}" == "true" && -n "${TRACE_PATH}" && -f "${TRACE_PATH}" ]]; then
    echo ""
    echo "--- REPLAY ---"
    bash scripts/test/replay_runtime_trace_mac.sh "${TRACE_PATH}"
fi
