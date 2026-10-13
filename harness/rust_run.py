"""Run the Rust/C backend twice, retaining raw evidence and Phase A evaluation."""

import argparse
import csv
import json
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path

from sim.config import Config
from sim.run import REPO, Execution, sha256

from .c32 import ControllerC32
from .run import publish
from .virtual_board import launch


def capture_rust(cfg, executable, build, raw_directory, backend="ffi", port=None, receipt=None):
    command = [
        str(Path(executable).resolve()),
        "--backend",
        "tcp" if backend == "virtual" else backend,
        "--python",
        sys.executable,
        "--build",
        str(Path(build).resolve()),
        "--output",
        str(raw_directory),
        "--contact-profile",
        cfg.contact_profile,
    ]
    raw_directory.mkdir(parents=True, exist_ok=False)
    if backend == "serial":
        if port is None or receipt is None:
            raise ValueError("serial requires port and verified flash receipt")
        command.extend(["--port", port, "--board-evidence", str(Path(receipt).resolve())])
    # Individual pipe requests have bounded deadlines; this is a final process
    # guard. A timeout remains INVALID and cannot publish a completed metrics run.
    try:
        with ExitStack() as stack:
            if backend == "virtual":
                address, virtual_metadata = stack.enter_context(
                    launch(build, raw_directory.with_name(raw_directory.name + "_board"))
                )
                command.extend(["--address", address])
            result = subprocess.run(command, cwd=REPO, capture_output=True, timeout=180)
            (raw_directory / "stdout.log").write_bytes(result.stdout)
            (raw_directory / "stderr.log").write_bytes(result.stderr)
            if result.returncode:
                raise ValueError(f"Rust run INVALID; see {raw_directory}")
    except subprocess.TimeoutExpired as exc:
        (raw_directory / "failure.json").write_text(
            json.dumps({"status": "INVALID", "error": "Rust process timeout"}) + "\n"
        )
        raise ValueError("Rust process timeout; partial evidence retained") from exc
    except (ValueError, OSError) as exc:
        (raw_directory / "failure.json").write_text(
            json.dumps({"status": "INVALID", "error": str(exc)}) + "\n"
        )
        raise
    completion = json.loads((raw_directory / "completion.json").read_text())
    if backend == "virtual":
        if (
            completion["controller"]["info"]["controller_source_sha256"]
            != virtual_metadata["controller_source_sha256"]
        ):
            raise ValueError("virtual-board source identity mismatch")
        if completion["controller"]["info"]["git_commit"] != virtual_metadata["git_commit"]:
            raise ValueError("virtual-board commit identity mismatch")
        completion["virtual_build"] = virtual_metadata
    if completion["status"] != "COMPLETE" or completion["completed_ticks"] != 8000:
        raise ValueError("incomplete Rust run")
    trace = (raw_directory / "trace.jsonl").read_bytes()
    truth = (raw_directory / "truth.jsonl").read_bytes()
    if (sha256(trace), sha256(truth)) != (completion["trace_sha256"], completion["truth_sha256"]):
        raise ValueError("Rust artifact checksum mismatch")
    rows = [json.loads(line) for line in truth.splitlines()]
    with (raw_directory / "wall_time.csv").open(newline="") as handle:
        times = list(csv.DictReader(handle))
    if len(rows) != 8000 or [int(row["tick"]) for row in times] != list(range(8000)):
        raise ValueError("Rust tick count mismatch")
    wall = [int(row["wall_time_ns"]) for row in times]
    if any(value <= 0 for value in wall):
        raise ValueError("invalid Rust wall-clock duration")
    return Execution(trace, truth, rows, wall, 8000, True, False, None), completion


def run(cfg, output, build, executable, backend="ffi"):
    if backend not in ("ffi", "virtual"):
        raise ValueError("unsupported repeatable host backend")
    if cfg != Config(controller="preview", contact_profile=cfg.contact_profile):
        raise ValueError("Rust runs require nominal seed-42 configuration")
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory must be empty")
    raw = output.with_name(output.name + "_raw")
    raw.mkdir(parents=True, exist_ok=False)
    first, first_report = capture_rust(cfg, executable, build, raw / "first", backend)
    second, second_report = capture_rust(cfg, executable, build, raw / "repeat", backend)
    controller = ControllerC32(build)
    if (
        backend == "ffi"
        and any(
            report["controller"]["controller_build"] != controller.build
            for report in (first_report, second_report)
        )
    ) or first_report["runtime"] != second_report["runtime"]:
        raise ValueError("Rust/ctypes C build or repeat Rust executable mismatch")
    if backend == "virtual" and any(
        report["virtual_build"] != controller.build["virtual"]
        for report in (first_report, second_report)
    ):
        raise ValueError("virtual-board build changed between repetitions")
    return publish(
        cfg,
        output,
        first,
        second,
        controller,
        runtime_provenance={
            "backend": "rust-" + backend,
            "runtime": first_report["runtime"],
            "virtual_build": first_report.get("virtual_build"),
        },
        wall_scope=first_report["wall_time_scope"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=("ffi", "virtual"), default="ffi")
    parser.add_argument(
        "--contact-profile", choices=("primary", "paper_effective"), default="primary"
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                Config(controller="preview", contact_profile=args.contact_profile),
                args.output,
                args.build,
                args.executable,
                args.backend,
            ),
            indent=2,
        )
    )
