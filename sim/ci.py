"""The single entry point used by GitHub Actions and local verification."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from .config import CONTACT_TARGETS_N_PER_M, CONTROLLERS
from .run import REPO, git_provenance, platform_fingerprint

REPRODUCTION_PATH = Path(__file__).with_name("reproduction_contract.json")
REPRODUCTION = json.loads(REPRODUCTION_PATH.read_text(encoding="utf-8"))


def reference_trace_hashes(fingerprint: dict | None = None) -> dict | None:
    fingerprint = platform_fingerprint() if fingerprint is None else fingerprint
    for baseline in REPRODUCTION["lab_frame_pd"]["platform_baselines"]:
        if baseline["platform_fingerprint"] == fingerprint:
            return baseline["trace_sha256"]
    return None


def reproduction_checks(metrics: dict, trace_hash: str) -> dict[str, bool]:
    controller = metrics["controller"]
    profile = metrics["contact_profile"]
    limits = REPRODUCTION[controller]
    if controller == "lab_frame_pd":
        low, high = limits["contact_rms_e_um_range"]
        hashes = reference_trace_hashes(metrics.get("platform_fingerprint"))
        return {
            "lab_frame_contact_rms_in_250_to_300_um": low <= metrics["contact"]["rms_e_um"] <= high,
            "platform_baseline_trace_matches_when_registered": (
                hashes is None or trace_hash == hashes[profile]
            ),
        }
    low, high = limits["free_rms_e_um_range"]
    checks = {"delayed_free_rms_near_20_um": low <= metrics["free"]["rms_e_um"] <= high}
    if profile == "primary":
        low, high = limits["primary_contact_rms_e_um_range"]
        checks["delayed_primary_contact_rms_in_150_to_200_um"] = (
            low <= metrics["contact"]["rms_e_um"] <= high
        )
    return checks


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
        commands.append(
            [
                "-m",
                "sim.calibrate",
                "--contact-profile",
                profile,
                "--output",
                str(output / profile / "contact_calibration.json"),
            ]
        )
        for controller in CONTROLLERS:
            commands.append(
                [
                    "-m",
                    "sim.run",
                    "--controller",
                    controller,
                    "--contact-profile",
                    profile,
                    "--seed",
                    str(REPRODUCTION["seed"]),
                    "--output",
                    str(output / profile / controller),
                ]
            )
    report = {
        "status": "RUNNING",
        **git_provenance(),
        "platform_fingerprint": platform_fingerprint(),
        "historical_trace_baseline_registered": reference_trace_hashes() is not None,
        "commands": [],
        "contact_profile_matrix": list(profiles),
        "controller_matrix": list(CONTROLLERS),
        "reproduction_contract": REPRODUCTION,
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
        report["profiles"][profile] = {
            "calibration_passed": json.loads(
                (output / profile / "contact_calibration.json").read_text(encoding="utf-8")
            )["passed"],
            "controllers": {},
        }
        for controller in CONTROLLERS:
            experiment = output / profile / controller
            metrics = json.loads((experiment / "metrics.json").read_text(encoding="utf-8"))
            trace_hash = hashlib.sha256((experiment / "trace.jsonl").read_bytes()).hexdigest()
            repeated_hash = hashlib.sha256(
                (experiment / "repeat_trace.jsonl").read_bytes()
            ).hexdigest()
            checks = {
                "same_seed_identical_trace_sha256": (
                    trace_hash == repeated_hash == metrics["determinism"]["trace_sha256"]
                    and metrics["determinism"]["verified"]
                ),
                "requested_experiment": (
                    metrics["controller"] == controller
                    and metrics["contact_profile"] == profile
                    and metrics["seed"] == REPRODUCTION["seed"]
                ),
                "complete_8000_ticks": metrics["complete"] and metrics["completed_ticks"] == 8000,
                "no_safety_stop": not metrics["safety_stop"],
                "expected_baseline_task_fail": metrics["verdict"]["status"] == "FAIL",
                **reproduction_checks(metrics, trace_hash),
            }
            report["profiles"][profile]["controllers"][controller] = {
                "checks": checks,
                "trace_sha256": trace_hash,
                "task_verdict": metrics["verdict"]["status"],
                "free_rms_e_um": metrics["free"]["rms_e_um"],
                "contact_rms_e_um": metrics["contact"]["rms_e_um"],
                "peak_contact_force_mn": metrics["contact"]["peak_contact_force_mn"],
            }
    diagnostic_force = report["profiles"]["paper_effective"]["controllers"]["lab_frame_pd"][
        "peak_contact_force_mn"
    ]
    # A scientific expectation may be disproven while the verification software passes.
    # Preserve the original 2-4 mN expectation and expose the result, without fitting.
    report["diagnostic_expectation"] = {
        "paper_effective_peak_force_expected_mn": [2.0, 4.0],
        "measured_mn": diagnostic_force,
        "met": 2.0 <= diagnostic_force <= 4.0,
        "gates_ci": False,
    }
    passed = all(
        p["calibration_passed"]
        and all(all(c["checks"].values()) for c in p["controllers"].values())
        for p in report["profiles"].values()
    )
    report["status"] = "PASS" if passed else "FAIL"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"CI job commands: {report['status']}; all four baseline task verdicts: FAIL")
    print(f"Diagnostic 2-4 mN expectation met: {report['diagnostic_expectation']['met']}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
