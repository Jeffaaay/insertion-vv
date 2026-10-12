"""The single entry point used by GitHub Actions and local verification."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from .config import CONTACT_TARGETS_N_PER_M
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
    ]
    profiles = tuple(CONTACT_TARGETS_N_PER_M)
    for profile in profiles:
        commands.extend(
            [
                [
                    "-m",
                    "sim.calibrate",
                    "--contact-profile",
                    profile,
                    "--output",
                    str(output / profile / "contact_calibration.json"),
                ],
                [
                    "-m",
                    "sim.run",
                    "--contact-profile",
                    profile,
                    "--seed",
                    "42",
                    "--output",
                    str(output / profile / "lab_frame_pd"),
                ],
            ]
        )
    report = {
        "status": "RUNNING",
        **git_provenance(),
        "commands": [],
        "contact_profile_matrix": list(profiles),
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
    report["profiles"] = {}
    for profile in profiles:
        baseline = output / profile / "lab_frame_pd"
        metrics = json.loads((baseline / "metrics.json").read_text(encoding="utf-8"))
        trace_hash = hashlib.sha256((baseline / "trace.jsonl").read_bytes()).hexdigest()
        repeated_hash = hashlib.sha256((baseline / "repeat_trace.jsonl").read_bytes()).hexdigest()
        checks = {
            "same_seed_identical_trace_sha256": (
                trace_hash == repeated_hash == metrics["determinism"]["trace_sha256"]
                and metrics["determinism"]["verified"]
            ),
            "lab_frame_contact_rms_in_250_to_300_um": 250 <= metrics["contact"]["rms_e_um"] <= 300,
            "complete_8000_ticks": metrics["complete"] and metrics["completed_ticks"] == 8000,
            "expected_baseline_task_fail": metrics["verdict"]["status"] == "FAIL",
            "measured_contact_stiffness_passed": json.loads(
                (output / profile / "contact_calibration.json").read_text(encoding="utf-8")
            )["passed"],
        }
        report["profiles"][profile] = {
            "checks": checks,
            "trace_sha256": trace_hash,
            "task_verdict": metrics["verdict"]["status"],
            "peak_contact_force_mn": metrics["contact"]["peak_contact_force_mn"],
        }
    diagnostic_force = report["profiles"]["paper_effective"]["peak_contact_force_mn"]
    # A scientific expectation may be disproven while the verification software passes.
    # Preserve the original 2-4 mN expectation and expose the result, without fitting.
    report["diagnostic_expectation"] = {
        "paper_effective_peak_force_expected_mn": [2.0, 4.0],
        "measured_mn": diagnostic_force,
        "met": 2.0 <= diagnostic_force <= 4.0,
        "gates_ci": False,
    }
    report["status"] = (
        "PASS" if all(all(p["checks"].values()) for p in report["profiles"].values()) else "FAIL"
    )
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"CI job commands: {report['status']}; both baseline task verdicts: FAIL")
    print(f"Diagnostic 2-4 mN expectation met: {report['diagnostic_expectation']['met']}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
