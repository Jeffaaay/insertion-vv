"""Independent Phase B job, preserving the Phase A controller matrix."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from sim.config import Config
from sim.run import git_provenance
from sim.run import run as run_reference
from tools.build_controller import build

from .compare import compare
from .run import run
from .rust_run import run as run_rust


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("CI output must be empty; preserve prior runs")
    root.mkdir(parents=True, exist_ok=True)
    build(root / "controller-build")
    executable = Path("harness/target/release") / (
        "insertion-harness.exe" if os.name == "nt" else "insertion-harness"
    )
    if not executable.is_file():
        raise ValueError("build the Rust release harness before running CI")
    env = {**os.environ, "C32_BUILD": str(root / "controller-build")}
    subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "harness/tests", f"--junitxml={root / 'tests.xml'}"],
        env=env,
        check=True,
    )
    report = {"status": "PASS", **git_provenance(), "profiles": {}}
    for profile in ("primary", "paper_effective"):
        cfg = Config(controller="preview", contact_profile=profile)
        reference = run_reference(cfg, root / profile / "preview")
        c32 = run(cfg, root / profile / "preview_c32", root / "controller-build")
        comparison = compare(
            root / profile / "preview", root / profile / "preview_c32", reference=True
        )
        report["profiles"][profile] = {"reference": reference, "c32": c32, "comparison": comparison}
        rust = run_rust(cfg, root / profile / "rust_ffi", root / "controller-build", executable)
        ffi_comparison = compare(root / profile / "preview_c32", root / profile / "rust_ffi")
        report["profiles"][profile].update(rust_ffi=rust, ffi_comparison=ffi_comparison)
        if (
            ffi_comparison["comparison"] != "same-build-bitwise"
            or ffi_comparison["status"] != "PASS"
        ):
            report["status"] = "FAIL"
        if comparison["status"] != "PASS":
            report["status"] = "FAIL"
    (root / "ci_report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "profiles": {
                    key: {
                        "c32_contact": value["c32"]["contact"],
                        "verdict": value["c32"]["verdict"],
                        "max_deltas": value["comparison"]["max_absolute_deltas"],
                        "checks": value["comparison"]["checks"],
                    }
                    for key, value in report["profiles"].items()
                },
            },
            indent=2,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
