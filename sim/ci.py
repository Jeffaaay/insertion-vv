"""The single entry point used by GitHub Actions and local verification."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from .run import REPO, git_provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    commands = [
        ["-m", "pip", "check"],
        ["-m", "ruff", "check", "."],
        ["-m", "ruff", "format", "--check", "."],
        ["-m", "pytest", "-q", f"--junitxml={output / 'tests.xml'}"],
        ["-m", "sim.calibrate", "--output", str(output / "contact_calibration.json")],
        ["-m", "sim.run", "--seed", "42", "--output", str(output / "lab_frame_pd")],
    ]
    report = {
        "status": "RUNNING",
        **git_provenance(),
        "commands": [],
        "github_actions_executed": os.environ.get("GITHUB_ACTIONS") == "true",
    }
    report_path = output / "ci_report.json"
    for i, command in enumerate(commands):
        print(f"Running: python {' '.join(command)}", flush=True)
        result = subprocess.run(
            [sys.executable, *command],
            cwd=REPO,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        log = result.stdout + result.stderr
        (output / f"step_{i + 1}.log").write_text(log, encoding="utf-8")
        report["commands"].append({"command": ["python", *command], "exit_code": result.returncode})
        print(log, end="", flush=True)
        if result.returncode:
            report["status"] = "FAIL"
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            return 1
    baseline = output / "lab_frame_pd"
    metrics = json.loads((baseline / "metrics.json").read_text(encoding="utf-8"))
    trace_hash = hashlib.sha256((baseline / "trace.jsonl").read_bytes()).hexdigest()
    repeated_hash = hashlib.sha256((baseline / "repeat_trace.jsonl").read_bytes()).hexdigest()
    report["checks"] = {
        "same_seed_identical_trace_sha256": (
            trace_hash == repeated_hash == metrics["determinism"]["trace_sha256"]
            and metrics["determinism"]["verified"]
        ),
        "lab_frame_contact_rms_in_250_to_300_um": 250 <= metrics["contact"]["rms_e_um"] <= 300,
        "complete_8000_ticks": metrics["complete"] and metrics["completed_ticks"] == 8000,
        "expected_baseline_task_fail": metrics["verdict"]["status"] == "FAIL",
        "measured_contact_stiffness_passed": json.loads(
            (output / "contact_calibration.json").read_text(encoding="utf-8")
        )["passed"],
    }
    report["trace_sha256"] = trace_hash
    report["status"] = "PASS" if all(report["checks"].values()) else "FAIL"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    status = metrics["verdict"]["status"]
    print(f"CI job commands: {report['status']}; baseline task verdict: {status}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
