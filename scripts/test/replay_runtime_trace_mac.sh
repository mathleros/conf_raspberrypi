#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_ROOT}"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" || $# -lt 1 ]]; then
    echo "Usage: $0 <trace_jsonl_path>"
    echo ""
    echo "Affiche un replay lisible d'un trace runtime JSONL généré par VoiceRuntime.handle_text_as_plan()."
    echo "Exemple :"
    echo "  bash $0 target/logs/runtime_trace_20261024T120000Z.jsonl"
    exit 0
fi

TRACE_PATH="$1"

if [[ ! -f "${TRACE_PATH}" ]]; then
    echo "Trace introuvable: ${TRACE_PATH}"
    exit 1
fi

PYTHONPATH=src uv run python - "$TRACE_PATH" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

trace = Path(sys.argv[1])
print(f"Replay: {trace}")
print("")

for line in trace.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    event = json.loads(line)
    ts = event.get("timestamp", "?")
    et = event.get("event", "?")

    if et == "input":
        print(f"[{ts}] INPUT: {event.get('text')}")
    elif et == "plan_raw":
        intents = event.get("intents", [])
        print(f"[{ts}] PLAN_RAW: {len(intents)} step(s), source={event.get('source')}")
    elif et == "plan_validated":
        intents = event.get("intents", [])
        errors = event.get("validation_errors", [])
        print(f"[{ts}] PLAN_VALIDATED: {len(intents)} valid step(s), errors={len(errors)}")
    elif et == "step_result":
        intent = event.get("intent", {})
        print(
            f"[{ts}] STEP: {intent.get('name')} attempt={event.get('attempt')} "
            f"status={event.get('status')} duration={event.get('duration_seconds')}s"
        )
    elif et == "mission_timeout":
        print(f"[{ts}] MISSION_TIMEOUT")
    elif et == "mission_result":
        print(
            f"[{ts}] MISSION_RESULT: status={event.get('status')} "
            f"duration={event.get('duration_seconds')}s steps={event.get('steps_count')}"
        )
    else:
        print(f"[{ts}] {et}: {event}")
PY
