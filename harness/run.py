"""Phase B C32 execution with frozen MuJoCo/sensors/evaluation functions."""

import argparse
import json
import time
import uuid
from dataclasses import asdict
from pathlib import Path

import numpy as np

from sim.config import Config
from sim.metrics import CONTRACT, CONTRACT_PATH, verdict, window_metrics
from sim.plant import MODEL_PATH, MujocoPlant, build_model, contact_parameters
from sim.platform_info import platform_fingerprint
from sim.reference import reference
from sim.run import REPO, Execution, canonical, git_provenance, sha256, source_hash

from .c32 import ControllerC32


def phase_b_source_hash():
    paths = sorted((REPO / "harness").glob("*.py"))
    paths += [
        REPO / "firmware/ctrl/controller.c",
        REPO / "firmware/ctrl/controller.h",
        REPO / "tools/build_controller.py",
        REPO / "harness/Cargo.toml",
        REPO / "harness/Cargo.lock",
        REPO / "harness/build.rs",
    ]
    paths += sorted((REPO / "harness/src").glob("*.rs"))
    paths += sorted((REPO / "firmware/protocol").glob("*.c"))
    paths += sorted((REPO / "firmware/protocol").glob("*.h"))
    paths += [REPO / "firmware/virtual_board/main.c"]
    paths += sorted((REPO / "firmware/h723").glob("*.c"))
    paths += sorted((REPO / "firmware/h723").glob("*.h"))
    paths += [
        REPO / "firmware/h723/linker.ld",
        REPO / "firmware/deps.lock.json",
        REPO / "tools/build_firmware.py",
    ]
    return sha256(
        source_hash().encode()
        + b"".join(
            str(p.relative_to(REPO)).replace("\\", "/").encode() + b"\0" + p.read_bytes()
            for p in paths
        )
    )


def evaluation_row(cfg, sensors, truth):
    gap, velocity = reference(
        sensors.time_us, cfg.initial_height_m, cfg.hover_height_m, cfg.insertion_depth_m
    )
    return {
        "tick": sensors.tick,
        "time_us": sensors.time_us,
        **asdict(truth),
        "reference_gap_m": gap,
        "reference_velocity_m_s": velocity,
        "e_m": gap - (truth.needle_z_m - truth.tissue_z_m),
        "edot_m_s": velocity - (truth.needle_v_m_s - truth.tissue_v_m_s),
    }


def capture(cfg, controller, write_truth=True):
    plant = MujocoPlant(cfg)
    trace, truth_trace, rows, wall_ns = [], [], [], []
    error, safety_stop = None, False
    controller.reset()
    try:
        for _ in range(cfg.duration_us // cfg.control_dt_us):
            start = time.perf_counter_ns()
            sensors = plant.sensors
            command = controller.command(sensors)
            row = evaluation_row(cfg, sensors, plant.truth())
            plant.step(command, cfg.control_dt_us)
            elapsed = time.perf_counter_ns() - start
            if not plant.healthy():
                safety_stop = True
                raise RuntimeError("MuJoCo warning or nonfinite state")
            trace.append(canonical({"sensors": asdict(sensors), "command": asdict(command)}))
            encoded = canonical(row)
            if write_truth:
                truth_trace.append(encoded)
            rows.append(row)
            wall_ns.append(elapsed)
    except (ValueError, RuntimeError, FloatingPointError, OSError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    return Execution(
        b"".join(trace),
        b"".join(truth_trace),
        rows,
        wall_ns,
        len(rows),
        len(rows) == cfg.duration_us // cfg.control_dt_us,
        safety_stop,
        error,
    )


def publish(cfg, output, first, second, controller, runtime_provenance=None, wall_scope=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("output directory must be empty; preserve previous evidence")
    effective = {
        "parameters": {**asdict(cfg), "controller": "preview_c32"},
        "c32_parameters": controller.parameter_values(),
        "contact": contact_parameters(build_model(cfg), cfg.contact_profile),
        "mjcf_sha256": sha256(MODEL_PATH.read_bytes()),
        "verdict_contract_sha256": sha256(CONTRACT_PATH.read_bytes()),
        "phase_b_contract": json.loads((REPO / "harness/contract.json").read_text()),
    }
    trace_hash, repeat_hash = sha256(first.trace), sha256(second.trace)
    truth_hash = sha256(b"".join(canonical(row) for row in first.rows))
    repeat_truth_hash = sha256(b"".join(canonical(row) for row in second.rows))
    reproducible = (
        first.complete
        and second.complete
        and trace_hash == repeat_hash
        and (truth_hash == repeat_truth_hash)
    )
    complete = first.complete and second.complete
    output.joinpath("config.json").write_bytes(canonical(effective))
    output.joinpath("trace.jsonl").write_bytes(first.trace)
    output.joinpath("repeat_trace.jsonl").write_bytes(second.trace)
    if first.truth_trace:
        output.joinpath("truth.jsonl").write_bytes(first.truth_trace)
    output.joinpath("trace.sha256").write_text(trace_hash + "  trace.jsonl\n", encoding="ascii")
    output.joinpath("wall_time.csv").write_bytes(
        ("tick,wall_time_ns\n" + "".join(f"{i},{n}\n" for i, n in enumerate(first.wall_ns))).encode(
            "ascii"
        )
    )
    contact = window_metrics(first.rows, *CONTRACT["contact_window_us"])
    times = np.asarray(first.wall_ns, dtype=float) / 1000
    metrics = {
        "schema_version": 1,
        "run_id": str(uuid.uuid4()),
        "controller": "preview_c32",
        "contact_profile": cfg.contact_profile,
        "contact_parameters": effective["contact"],
        "seed": cfg.seed,
        **git_provenance(),
        "source_sha256": phase_b_source_hash(),
        "config_sha256": sha256(canonical(effective)),
        "platform_fingerprint": platform_fingerprint(),
        "controller_build": controller.build,
        "duration_s": cfg.duration_us / 1e6,
        "control_dt_us": cfg.control_dt_us,
        "physics_dt_us": cfg.physics_dt_us,
        "completed_ticks": first.completed_ticks,
        "complete": complete,
        "safety_stop": first.safety_stop,
        "error": first.error or second.error,
        "free": window_metrics(first.rows, *CONTRACT["free_window_us"]),
        "contact": contact,
        "whole_run_peak_abs_edot_mm_s": max(
            (abs(r["edot_m_s"]) * 1e3 for r in first.rows), default=None
        ),
        "whole_run_peak_contact_force_mn": max(
            (r["contact_force_n"] * 1e3 for r in first.rows), default=None
        ),
        "wall_time_us": {
            "samples": len(first.wall_ns),
            "per_tick_file": "wall_time.csv",
            "scope": wall_scope or "C32 adapter + evaluation + MuJoCo/sensors; excludes file I/O",
            "mean": float(times.mean()) if times.size else None,
            "p50": float(np.percentile(times, 50)) if times.size else None,
            "p95": float(np.percentile(times, 95)) if times.size else None,
            "max": float(times.max()) if times.size else None,
        },
        "determinism": {
            "verified": bool(reproducible),
            "trace_sha256": trace_hash,
            "repeat_trace_sha256": repeat_hash,
            "truth_sha256": truth_hash,
            "repeat_truth_sha256": repeat_truth_hash,
            "tier": "intra-platform-bitwise",
            "scope": "same full plant fingerprint AND controller build/source/config/seed",
        },
        "verdict_contract": CONTRACT,
        "verdict": verdict(
            contact, complete=complete, reproducible=reproducible, safety_stop=first.safety_stop
        ),
    }
    if runtime_provenance is not None:
        metrics["runtime_provenance"] = runtime_provenance
    output.joinpath("metrics.json").write_text(
        json.dumps(metrics, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return metrics


def run(cfg, output, build_directory, write_truth=True):
    if cfg != Config(controller="preview", contact_profile=cfg.contact_profile):
        raise ValueError("B1 C32 runs require the registered nominal seed-42 configuration")
    if Path(output).exists() and any(Path(output).iterdir()):
        raise ValueError("output directory must be empty")
    controller = ControllerC32(build_directory)
    first = capture(cfg, controller, write_truth)
    second = capture(cfg, controller, write_truth)
    return publish(cfg, output, first, second, controller)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--contact-profile", choices=("primary", "paper_effective"), default="primary"
    )
    parser.add_argument("--no-truth", action="store_true")
    args = parser.parse_args()
    result = run(
        Config(controller="preview", contact_profile=args.contact_profile),
        args.output,
        args.build,
        not args.no_truth,
    )
    print(json.dumps(result, indent=2))
    raise SystemExit(2 if result["verdict"]["status"] == "INVALID" else 0)
