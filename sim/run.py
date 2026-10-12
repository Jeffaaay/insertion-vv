"""Run lab_frame_pd twice and publish measured, reproducibility-checked artifacts."""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import mujoco
import numpy as np

from .config import CONTACT_TARGETS_N_PER_M, Config
from .controllers import LabFramePD
from .metrics import CONTRACT, CONTRACT_PATH, verdict, window_metrics
from .plant import MODEL_PATH, MujocoPlant, build_model, contact_parameters
from .reference import reference

REPO = Path(__file__).resolve().parents[1]


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass
class Execution:
    trace: bytes
    truth_trace: bytes
    rows: list[dict]
    wall_ns: list[int]
    completed_ticks: int
    complete: bool
    safety_stop: bool
    error: str | None


def simulate(cfg: Config, *, write_truth: bool = True) -> Execution:
    cfg.validate()
    plant = MujocoPlant(cfg)
    controller = LabFramePD(
        cfg.kp_n_per_m,
        cfg.kd_ns_per_m,
        cfg.initial_height_m,
        cfg.hover_height_m,
        cfg.insertion_depth_m,
    )
    trace, truth_trace, rows, wall_ns = [], [], [], []
    completed_ticks = 0
    error = None
    safety_stop = False
    expected_ticks = cfg.duration_us // cfg.control_dt_us
    try:
        for tick in range(expected_ticks):
            start_ns = time.perf_counter_ns()
            sensors = plant.sensors
            command = controller.command(sensors)
            truth = plant.truth()
            z_ref, v_ref = reference(
                sensors.time_us, cfg.initial_height_m, cfg.hover_height_m, cfg.insertion_depth_m
            )
            row = {
                "tick": tick,
                "time_us": sensors.time_us,
                **asdict(truth),
                "reference_gap_m": z_ref,
                "reference_velocity_m_s": v_ref,
                "e_m": z_ref - (truth.needle_z_m - truth.tissue_z_m),
                "edot_m_s": v_ref - (truth.needle_v_m_s - truth.tissue_v_m_s),
            }
            plant.step(command, cfg.control_dt_us)
            elapsed_ns = time.perf_counter_ns() - start_ns
            if not plant.healthy():
                safety_stop = True
                raise RuntimeError("MuJoCo warning or nonfinite state")
            # File serialization and timing are outside the control/plant path.
            trace.append(canonical({"sensors": asdict(sensors), "command": asdict(command)}))
            encoded_truth = canonical(row)  # Also rejects nonfinite evaluator data.
            if write_truth:
                truth_trace.append(encoded_truth)
            rows.append(row)
            wall_ns.append(elapsed_ns)
            completed_ticks += 1
    except (ValueError, RuntimeError, FloatingPointError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    return Execution(
        b"".join(trace),
        b"".join(truth_trace),
        rows,
        wall_ns,
        completed_ticks,
        completed_ticks == expected_ticks,
        safety_stop,
        error,
    )


def git_provenance() -> dict:
    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", *args], cwd=REPO, stderr=subprocess.DEVNULL, text=True
        ).strip()

    try:
        return {
            "git_sha": git("rev-parse", "HEAD"),
            "git_dirty": bool(git("status", "--porcelain")),
        }
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"git_sha": None, "git_dirty": True}


def source_hash() -> str:
    paths = sorted((REPO / "sim").glob("*.py"))
    paths += [REPO / "requirements.txt", REPO / "requirements-lock.txt"]
    return sha256(b"".join(p.name.encode() + b"\0" + p.read_bytes() for p in paths))


def run(cfg: Config, output: Path, *, write_truth: bool = True) -> dict:
    cfg.validate()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("output directory must be empty; preserve previous run evidence")
    effective_config = {
        "parameters": asdict(cfg),
        "contact": contact_parameters(build_model(cfg), cfg.contact_profile),
        "mjcf_sha256": sha256(MODEL_PATH.read_bytes()),
        "verdict_contract_sha256": sha256(CONTRACT_PATH.read_bytes()),
    }
    (output / "config.json").write_bytes(canonical(effective_config))
    first = simulate(cfg, write_truth=write_truth)
    second = simulate(cfg, write_truth=write_truth)
    trace_hash = sha256(first.trace)
    repeat_hash = sha256(second.trace)
    same_trace = trace_hash == repeat_hash
    # Evaluator truth is checked even when its optional file output is disabled.
    truth_hash = sha256(b"".join(canonical(r) for r in first.rows))
    repeat_truth_hash = sha256(b"".join(canonical(r) for r in second.rows))
    reproducible = (
        first.complete and second.complete and same_trace and truth_hash == repeat_truth_hash
    )
    (output / "trace.jsonl").write_bytes(first.trace)
    (output / "repeat_trace.jsonl").write_bytes(second.trace)
    if write_truth:
        (output / "truth.jsonl").write_bytes(first.truth_trace)
    (output / "trace.sha256").write_text(trace_hash + "  trace.jsonl\n", encoding="ascii")
    timing_csv = "tick,wall_time_ns\n" + "".join(f"{i},{n}\n" for i, n in enumerate(first.wall_ns))
    (output / "wall_time.csv").write_bytes(timing_csv.encode("ascii"))
    free = window_metrics(first.rows, *CONTRACT["free_window_us"])
    contact = window_metrics(first.rows, *CONTRACT["contact_window_us"])
    expected_ticks = cfg.duration_us // cfg.control_dt_us
    complete = (
        first.complete
        and second.complete
        and len(first.rows) == expected_ticks
        and [r["tick"] for r in first.rows] == list(range(expected_ticks))
    )
    times_us = np.asarray(first.wall_ns, dtype=float) / 1000
    metrics = {
        "schema_version": 1,
        "run_id": str(uuid.uuid4()),
        "controller": cfg.controller,
        "contact_profile": cfg.contact_profile,
        "contact_parameters": effective_config["contact"],
        "seed": cfg.seed,
        **git_provenance(),
        "source_sha256": source_hash(),
        "config_sha256": sha256(canonical(effective_config)),
        "environment": {
            "python": platform.python_version(),
            "mujoco": mujoco.__version__,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "duration_s": cfg.duration_us / 1e6,
        "control_dt_us": cfg.control_dt_us,
        "physics_dt_us": cfg.physics_dt_us,
        "completed_ticks": first.completed_ticks,
        "complete": complete,
        "safety_stop": first.safety_stop,
        "error": first.error,
        "free": free,
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
            "scope": "controller + truth evaluation + plant step + sensor model; excludes file I/O",
            "mean": float(np.mean(times_us)) if times_us.size else None,
            "p50": float(np.percentile(times_us, 50)) if times_us.size else None,
            "p95": float(np.percentile(times_us, 95)) if times_us.size else None,
            "max": float(np.max(times_us)) if times_us.size else None,
        },
        "determinism": {
            "verified": bool(reproducible),
            "trace_sha256": trace_hash,
            "repeat_trace_sha256": repeat_hash,
            "truth_sha256": truth_hash,
            "repeat_truth_sha256": repeat_truth_hash,
            "scope": "same environment/config/seed; wall-time and run metadata excluded",
        },
        "verdict_contract": CONTRACT,
        "verdict": verdict(
            contact,
            complete=complete,
            reproducible=bool(reproducible),
            safety_stop=first.safety_stop,
        ),
    }
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--contact-profile", choices=CONTACT_TARGETS_N_PER_M, default="primary")
    parser.add_argument("--sample-hz", type=int, choices=(25, 1000), default=1000)
    parser.add_argument("--noise-std-m", type=float, default=0.0)
    parser.add_argument("--dropout-probability", type=float, default=0.0)
    parser.add_argument("--no-truth", action="store_true")
    args = parser.parse_args()
    cfg = Config(
        seed=args.seed,
        contact_profile=args.contact_profile,
        surface_sample_hz=args.sample_hz,
        surface_noise_std_m=args.noise_std_m,
        surface_dropout_probability=args.dropout_probability,
    )
    try:
        metrics = run(cfg, args.output, write_truth=not args.no_truth)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(metrics, indent=2, allow_nan=False))
    # The intentionally poor baseline is expected to FAIL the task contract.
    # Only INVALID is an execution error; CI checks regression ranges separately.
    return 2 if metrics["verdict"]["status"] == "INVALID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
