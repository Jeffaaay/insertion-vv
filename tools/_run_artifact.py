"""Read immutable run evidence for optional visualization; no simulation imports."""

import hashlib
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_run(directory: Path) -> tuple[dict, dict, list[dict]]:
    directory = directory.resolve()
    metrics = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
    config_bytes = (directory / "config.json").read_bytes()
    if hashlib.sha256(config_bytes).hexdigest() != metrics["config_sha256"]:
        raise ValueError("config.json does not match the measured run's SHA-256")
    config = json.loads(config_bytes)
    if not metrics["complete"] or not metrics["determinism"]["verified"]:
        raise ValueError("Visualization requires a complete, reproducible run")
    truth = (directory / "truth.jsonl").read_bytes()
    if hashlib.sha256(truth).hexdigest() != metrics["determinism"]["truth_sha256"]:
        raise ValueError("truth.jsonl does not match the measured run's SHA-256")
    if (
        hashlib.sha256((directory / "trace.jsonl").read_bytes()).hexdigest()
        != metrics["determinism"]["trace_sha256"]
    ):
        raise ValueError("trace.jsonl does not match the measured run's SHA-256")
    rows = [json.loads(line) for line in truth.splitlines()]
    if len(rows) != metrics["completed_ticks"]:
        raise ValueError("Incomplete truth record")
    required = (
        "needle_z_m",
        "needle_v_m_s",
        "tissue_z_m",
        "tissue_v_m_s",
        "e_m",
        "edot_m_s",
        "contact_force_n",
    )
    for tick, row in enumerate(rows):
        if row["tick"] != tick or row["time_us"] != tick * metrics["control_dt_us"]:
            raise ValueError("Truth timestamps must be contiguous control ticks")
        if not all(math.isfinite(row[key]) for key in required):
            raise ValueError("Nonfinite truth record")
    return metrics, config, rows


def default_output(metrics: dict, extension: str) -> Path:
    name = f"{metrics['controller']}_{metrics['contact_profile']}_seed{metrics['seed']}"
    return REPO / "artifacts" / "viz" / f"{name}.{extension}"


def provenance(metrics: dict, run: Path) -> dict:
    return {
        "source_run": str(run.resolve()),
        "run_id": metrics["run_id"],
        "controller": metrics["controller"],
        "contact_profile": metrics["contact_profile"],
        "seed": metrics["seed"],
        "git_sha": metrics["git_sha"],
        "platform_fingerprint": metrics.get("platform_fingerprint"),
        "source_environment": metrics["environment"],
        "trace_sha256": metrics["determinism"]["trace_sha256"],
        "truth_sha256": metrics["determinism"]["truth_sha256"],
        "purpose": "Optional visualization of recorded states; not a CI or test dependency",
    }
