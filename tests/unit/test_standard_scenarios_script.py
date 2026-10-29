from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.parametrize("runner_fails", [False, True])
def test_standard_scenarios_yellow_ball_report(tmp_path, runner_fails):
    root = Path(__file__).resolve().parents[2]
    script = Path("scripts/test/run_runtime_standard_scenarios_mac.sh")
    (tmp_path / script.parent).mkdir(parents=True)
    shutil.copy2(root / script, tmp_path / script)
    for folder in ("src", "tests"):
        (tmp_path / folder).symlink_to(root / folder, target_is_directory=True)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # Keep the four LLM cases offline; the fifth runs the real runtime.
    bash = bin_dir / "bash"
    bash.write_text(
        "#!/bin/bash\n"
        "printf '%s\\n' \"{'status': 'accepted'}\" 'TRACE_PATH=mock-llm.jsonl'\n",
        encoding="utf-8",
    )
    uv = bin_dir / "uv"
    uv.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        + ("sys.exit(7)\n" if runner_fails else "os.execv(sys.executable, [sys.executable, *sys.argv[3:]])\n"),
        encoding="utf-8",
    )
    bash.chmod(0o755)
    uv.chmod(0o755)
    completed = subprocess.run(
        ["/bin/bash", str(tmp_path / script)],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=30,
    )

    reports = list((tmp_path / "target/logs/scenario_runs").glob("scenario_report_*.md"))
    assert len(reports) == 1
    report = reports[0].read_text(encoding="utf-8")
    if runner_fails:
        assert completed.returncode == 7
        assert "Yellow ball" not in report
        assert "Report generated:" not in completed.stdout
        return

    assert completed.returncode == 0, completed.stderr
    rows = [line for line in report.splitlines() if line.startswith("| ")]
    assert len(rows) == 6
    assert "| Yellow ball (mock, 300 s simulated) |" in rows[-1]
    assert "| accepted |" in rows[-1]
    trace = Path(rows[-1].split("|")[-2].strip())
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    steps = [event["intent"] for event in events if event["event"] == "step_result"]
    assert {step["name"] for step in steps} == {"search_and_approach_object", "follow_object"}
    follow = next(step for step in steps if step["name"] == "follow_object")
    assert follow["target"] == "yellow"
    assert follow["parameters"]["stand_off_cm"] == 100.0
    assert follow["parameters"]["duration_s"] == 300.0
    assert f"TRACE_PATH={trace}" in completed.stdout
