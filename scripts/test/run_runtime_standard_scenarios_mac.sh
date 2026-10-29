#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_ROOT}"

OUT_DIR="${PROJECT_ROOT}/target/logs/scenario_runs"
mkdir -p "${OUT_DIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT="${OUT_DIR}/scenario_report_${STAMP}.md"

cat >"${REPORT}" <<EOF
# Scenario run report (${STAMP})

| Scenario | Command | Status | Trace |
|---|---|---|---|
EOF

run_case() {
    local name="$1"
    local text="$2"
    local mock_pos="${3:-}"

    local tmp_out
    tmp_out="$(mktemp)"

    if [[ -n "${mock_pos}" ]]; then
        bash scripts/test/run_llm_runtime_mac.sh --text "${text}" --mock-object-position "${mock_pos}" >"${tmp_out}"
    else
        bash scripts/test/run_llm_runtime_mac.sh --text "${text}" >"${tmp_out}"
    fi

    local status trace
    status="$(grep -E "'status':|\"status\":" "${tmp_out}" | head -n 1 | sed -E "s/.*status['\"]?: ['\"]?([a-zA-Z_]+).*/\1/" || true)"
    trace="$(grep -E '^TRACE_PATH=' "${tmp_out}" | sed 's/^TRACE_PATH=//' || true)"

    echo "| ${name} | ${text} | ${status:-unknown} | ${trace:-n/a} |" >>"${REPORT}"
    rm -f "${tmp_out}"
}

run_case "Forward 20cm" "avance de 20 cm"
run_case "Turn right 90" "tourne a droite de 90 degres"
run_case "Search and approach" "cherche un objet puis approche toi" "centre"
run_case "Obstacle contour" "contourne l'objet devant toi a 20 cm"

PYTHONPATH=src uv run python - "${OUT_DIR}" "${REPORT}" <<'PY'
from pathlib import Path
import sys

from tests.unit.test_scenario_yellow_ball import FOLLOW_S, SENTENCE, STAND_OFF_CM, TOLERANCE_CM, run_scenario

world, result, _, spans = run_scenario(Path(sys.argv[1]))
if result["status"] != "accepted" or result["mission"]["phase"] != "success":
    raise RuntimeError(f"Yellow ball scenario failed: {result}")

started, finished, follow = spans["follow_object"][0]
if (
    follow.status != "success"
    or follow.data["duration_s"] != FOLLOW_S
    or not FOLLOW_S <= finished - started < FOLLOW_S + 0.5
    or abs(follow.data["final_distance_cm"] - STAND_OFF_CM) > TOLERANCE_CM
    or world.targets != {"yellow"}
    or world.commands[-1] != "stop"
):
    raise RuntimeError(f"Yellow ball follow validation failed: {follow}")

trace = result["trace_path"]
with Path(sys.argv[2]).open("a", encoding="utf-8") as report:
    report.write(f"| Yellow ball (mock, 300 s simulated) | {SENTENCE} | accepted | {trace} |\n")
print(f"TRACE_PATH={trace}")
PY

echo "Report generated: ${REPORT}"
