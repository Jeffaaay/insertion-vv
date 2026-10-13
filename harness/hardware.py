"""Actual serial lockstep and recorded-input replay, gated by verified Flash evidence."""

import argparse
import json
import subprocess
from pathlib import Path

from sim.config import Config
from tools.board import fresh, save, sha, validate_firmware

from .c32 import ControllerC32
from .compare import compare
from .replay_report import analyze, extract_lockstep, percentiles
from .run import publish
from .rust_run import capture_rust


def evidence(firmware, receipt):
    build = validate_firmware(firmware)
    record = json.loads(Path(receipt).read_text())
    if (
        record["status"] != "FLASH_VERIFIED"
        or record["binary_sha256"] != build["binary_sha256"]
        or record["elf_sha256"] != build["elf_sha256"]
        or record["firmware_git"] != build["git_commit"]
        or sha(Path(record["readback_file"]).read_bytes()) != build["binary_sha256"]
    ):
        raise ValueError("missing or mismatched verified flash evidence")
    return build, record


def board_link(executable, firmware, receipt, port, output, inputs=None):
    command = [
        str(Path(executable).resolve()),
        "--build",
        str(Path(firmware).resolve()),
        "--board-evidence",
        str(Path(receipt).resolve()),
        "--port",
        port,
        "--output",
        str(Path(output).resolve()),
    ]
    if inputs is not None:
        command.extend(["--input", str(Path(inputs).resolve())])
    output = Path(output)
    try:
        result = subprocess.run(command, capture_output=True, timeout=180)
        output.mkdir(parents=True, exist_ok=True)
        (output / "stdout.log").write_bytes(result.stdout)
        (output / "stderr.log").write_bytes(result.stderr)
        if result.returncode:
            raise ValueError("board link INVALID; inspect retained raw output")
    except subprocess.TimeoutExpired as exc:
        output.mkdir(parents=True, exist_ok=True)
        (output / "stdout.log").write_bytes(exc.stdout or b"")
        (output / "stderr.log").write_bytes(exc.stderr or b"")
        raise ValueError("board link process deadline; partial evidence retained") from exc
    return json.loads((output / "completion.json").read_text())


class BoardDescription:
    """Metadata/parameters only. All command evaluation happened on the board."""

    def __init__(self, firmware, info, host_build):
        self.reference = ControllerC32(host_build)
        if self.reference.build["controller_source_sha256"] != firmware["controller_source_sha256"]:
            raise ValueError("host and firmware cores differ")
        self.build = {
            "sources": self.reference.build["sources"],
            # Retain comparison schema's build-platform key; this is explicitly ARM.
            "host": {
                "kind": "STM32H723-board",
                "unique_id_hex": info["unique_id_hex"],
                "compiler": firmware["compiler"],
                "flags": firmware["controller_flags"],
                "elf_sha256": firmware["elf_sha256"],
                "binary_sha256": firmware["binary_sha256"],
            },
            "firmware": firmware,
            "board_info": info,
        }

    def parameter_values(self):
        return self.reference.parameter_values()


def lockstep(args):
    build, receipt = evidence(args.firmware, args.receipt)
    root = fresh(args.output)
    identity = board_link(
        args.board_link, args.firmware, args.receipt, args.port, root / "identity"
    )
    if identity["status"] != "IDENTITY_VERIFIED":
        raise ValueError("board identity handshake did not pass")
    cfg = Config(controller="preview", contact_profile=args.contact_profile)
    captures = [
        capture_rust(
            cfg, args.executable, args.firmware, root / name, "serial", args.port, args.receipt
        )
        for name in ("first", "repeat")
    ]
    info = identity["controller"]["info"]
    if any(c[1]["controller"]["info"] != info for c in captures):
        raise ValueError("board identity changed between runs")
    if captures[0][1]["runtime"] != captures[1][1]["runtime"]:
        raise ValueError("host runtime changed between hardware repeats")
    description = BoardDescription(build, info, args.host_build)
    metrics = publish(
        cfg,
        root / "run",
        captures[0][0],
        captures[1][0],
        description,
        runtime_provenance={
            "backend": "rust-serial",
            "runtime": captures[0][1]["runtime"],
            "board_info": info,
            "flash_evidence": receipt,
            "identity_check": identity,
        },
        wall_scope=captures[0][1]["wall_time_scope"],
    )
    inputs, commands, rtt = extract_lockstep(root / "first", info)
    repeat_inputs, repeat_commands, _ = extract_lockstep(root / "repeat", info)
    if inputs != repeat_inputs or commands != repeat_commands:
        raise ValueError("same-board wire input/output bits did not reproduce")
    (root / "inputs.bin").write_bytes(inputs)
    (root / "expected-forces.bin").write_bytes(commands)
    comparison = compare(args.reference, root / "run")
    relative = comparison["metric_deltas"]["contact.rms_e_um"]["relative_difference"]
    checks = {
        "registered_C32_comparison": comparison["status"] == "PASS",
        "hardware_contact_rms_relative_below_1_percent": relative < 0.01,
        "same_board_repeats_bitwise": metrics["determinism"]["verified"],
    }
    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "metrics": metrics,
        "comparison": comparison,
        "uart_request_reply_us": percentiles(rtt),
        "uart_wire_minimum_us": 70 * 10 / 460800 * 1e6,
        "uart_RTT_scope": (
            "host monotonic TX-start to RX-complete; serialization, board compute, "
            "USB/driver/OS combined"
        ),
        "hardware_timing_verified": False,
        "input_sha256": sha(inputs),
        "force_bits_sha256": sha(commands),
    }
    save(root / "lockstep_report.json", report)
    return report


def replay(args):
    build, receipt = evidence(args.firmware, args.receipt)
    source = json.loads((args.lockstep / "lockstep_report.json").read_text())
    if source["status"] != "PASS":
        raise ValueError(
            "replay requires accepted actual lockstep, stop on a failed functional gate"
        )
    info = source["metrics"]["runtime_provenance"]["board_info"]
    if source["metrics"]["controller_build"]["firmware"] != build:
        raise ValueError("replay and lockstep firmware must be identical")
    inputs, commands, _ = extract_lockstep(args.lockstep / "first", info)
    if sha(inputs) != source["input_sha256"] or sha(commands) != source["force_bits_sha256"]:
        raise ValueError("lockstep evidence changed")
    root = fresh(args.output)
    (root / "inputs.bin").write_bytes(inputs)
    (root / "expected-forces.bin").write_bytes(commands)
    captured = board_link(
        args.board_link, args.firmware, args.receipt, args.port, root / "raw", root / "inputs.bin"
    )
    if captured["status"] != "COMPLETE" or captured["controller"]["info"] != info:
        raise ValueError("replay incomplete or board identity changed")
    raw_commands = (root / "raw/commands.bin").read_bytes()
    timing = (root / "raw/timing.bin").read_bytes()
    if (
        sha(raw_commands) != captured["command_telemetry_sha256"]
        or sha(timing) != captured["timing_sha256"]
    ):
        raise ValueError("replay artifact checksum mismatch")
    report = analyze(raw_commands, timing, commands, inputs, captured["summary_words"])
    report.update(
        firmware=build,
        flash_evidence=receipt,
        raw_completion=captured,
        contact_profile=source["metrics"]["contact_profile"],
        seed=42,
        hardware_timing_verified=report["status"] == "PASS",
    )
    save(root / "timing_report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("lockstep", "replay"))
    parser.add_argument("--firmware", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--port", required=True)
    parser.add_argument("--board-link", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--host-build", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--lockstep", type=Path)
    parser.add_argument(
        "--contact-profile", choices=("primary", "paper_effective"), default="primary"
    )
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        print(
            json.dumps(
                {"status": "INVALID", "error": "output must be empty; prior evidence preserved"}
            )
        )
        return 2
    try:
        required = (
            (args.executable, args.host_build, args.reference)
            if args.action == "lockstep"
            else (args.lockstep,)
        )
        if any(v is None for v in required):
            raise ValueError("missing mode-specific paths; see hardware runbook")
        result = lockstep(args) if args.action == "lockstep" else replay(args)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        result = {"status": "INVALID", "error": str(exc)}
        with (args.output / "failure.json").open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
    print(json.dumps({"status": result["status"], "output": str(args.output)}, indent=2))
    return {"PASS": 0, "FAIL": 1, "INVALID": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
