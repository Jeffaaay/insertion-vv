"""Execute registered scenarios through frozen controllers and verdict functions."""

import gzip
import json
import time
import uuid
from dataclasses import asdict, replace
from pathlib import Path

from harness.c32 import ControllerC32
from harness.run import evaluation_row
from sim.config import Config
from sim.contracts import Command
from sim.controllers import (
    AccelerationBiasObserver,
    DelayedFeedback,
    DelayedFeedbackOffsetFree,
    LabFramePD,
)
from sim.metrics import CONTRACT, verdict, window_metrics
from sim.preview import HarmonicSurfaceEstimator, PreviewFeedback
from sim.run import Execution, canonical, sha256

from .plant import FaultPlant


def scenario(controller="preview", fault="none", level=0, onset_ms=0, seed=42, ablation="baseline"):
    return dict(
        controller=controller,
        fault=fault,
        level=level,
        onset_ms=onset_ms,
        seed=seed,
        ablation=ablation,
        contact_profile="primary",
    )


def run_id(case):
    return sha256(canonical(case))[:24]


def controller_for(cfg, name, build):
    if name == "preview_c32":
        return ControllerC32(Path(build))
    if name == "lab_frame_pd":
        return LabFramePD(
            cfg.kp_n_per_m,
            cfg.kd_ns_per_m,
            cfg.initial_height_m,
            cfg.hover_height_m,
            cfg.insertion_depth_m,
        )
    args = (
        cfg.delayed_kp_n_per_m,
        cfg.delayed_kd_ns_per_m,
        cfg.initial_height_m,
        cfg.hover_height_m,
        cfg.insertion_depth_m,
        cfg.surface_velocity_filter_tau_us,
    )
    control = DelayedFeedback(*args)
    if name == "preview":
        control = PreviewFeedback(
            *args,
            HarmonicSurfaceEstimator(
                cfg.preview_frequencies_hz,
                cfg.preview_delay_us,
                cfg.preview_initial_std_m,
                cfg.preview_measurement_std_m,
                cfg.preview_process_std_m_sqrt_s,
            ),
        )
    if name in ("preview", "delayed_feedback_offsetfree"):
        control = DelayedFeedbackOffsetFree(
            control,
            AccelerationBiasObserver(
                cfg.observer_mass_kg,
                cfg.control_dt_us * 1e-6,
                cfg.observer_gain_position,
                cfg.observer_gain_velocity,
                cfg.observer_gain_acceleration,
            ),
        )
    return control


def execute(case, build=None, nominal_peak=None):
    cfg = Config(
        controller="preview" if case["controller"] == "preview_c32" else case["controller"],
        seed=case["seed"],
    )
    plant = FaultPlant(cfg, case)
    control = controller_for(cfg, case["controller"], build)
    trace, truth_trace, rows = [], [], []
    previous = Command(0.0)
    mailbox = None
    error, safety_stop = None, False
    peak = 0.0
    try:
        for tick in range(8000):
            sensors = plant.sensors
            if plant.injector.skip(tick):
                if sensors.surface_fresh:
                    mailbox = sensors
                command = previous
            else:
                if mailbox is not None and not sensors.surface_fresh:
                    sensors = replace(
                        sensors,
                        surface_z_m=mailbox.surface_z_m,
                        surface_sample_time_us=mailbox.surface_sample_time_us,
                        surface_sequence=mailbox.surface_sequence,
                        surface_fresh=True,
                    )
                mailbox = None
                command = control.command(sensors)
            command = Command(plant.injector.clip(tick, command.force_n, nominal_peak))
            previous = command
            peak = max(peak, abs(command.force_n))
            row = evaluation_row(cfg, sensors, plant.truth())
            plant.step(command, cfg.control_dt_us)
            if not plant.healthy():
                safety_stop = True
                raise RuntimeError("MuJoCo warning or nonfinite state")
            trace.append(canonical({"sensors": asdict(sensors), "command": asdict(command)}))
            truth_trace.append(canonical(row))
            rows.append(row)
    except (ValueError, RuntimeError, FloatingPointError, OSError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    result = Execution(
        b"".join(trace),
        b"".join(truth_trace),
        rows,
        [],
        len(rows),
        len(rows) == 8000,
        safety_stop,
        error,
    )
    return result, peak


def measured_run(case, output, build=None, nominal=None, provenance=None):
    start = time.monotonic()
    identity = run_id(case)
    directory = Path(output) / "runs" / identity
    if case["fault"] == "F7":
        expected = scenario(controller=case["controller"], ablation=case["ablation"])
        if (
            nominal is None
            or nominal["scenario"] != expected
            or nominal["verdict"]["status"] == "INVALID"
        ):
            raise ValueError("F7 nominal must be valid same-controller/ablation seed-42 no-fault")
    if directory.exists():
        row = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
        if row["scenario"] != case or row["provenance"] != provenance:
            raise ValueError("resume provenance mismatch")
        for stem in ("trace", "truth"):
            data = gzip.decompress((directory / f"{stem}.jsonl.gz").read_bytes())
            if sha256(data) != row[f"{stem}_sha256"]:
                raise ValueError("corrupt resumed trace")
        return row
    peak_reference = nominal["peak_abs_command_n"] if nominal is not None else None
    first, peak = execute(case, build, peak_reference)
    second, _ = execute(case, build, peak_reference)
    hashes = {
        "trace_sha256": sha256(first.trace),
        "truth_sha256": sha256(first.truth_trace),
        "repeat_trace_sha256": sha256(second.trace),
        "repeat_truth_sha256": sha256(second.truth_trace),
    }
    reproducible = (
        first.complete
        and second.complete
        and hashes["trace_sha256"] == hashes["repeat_trace_sha256"]
        and hashes["truth_sha256"] == hashes["repeat_truth_sha256"]
    )
    contact = window_metrics(first.rows, *CONTRACT["contact_window_us"])
    status = verdict(
        contact,
        complete=first.complete and second.complete,
        reproducible=reproducible,
        safety_stop=first.safety_stop or second.safety_stop,
    )
    row = {
        "run_id": identity,
        "scenario": case,
        **hashes,
        "provenance": provenance,
        "contact": contact,
        "free": window_metrics(first.rows, *CONTRACT["free_window_us"]),
        "verdict": status,
        "completed_ticks": first.completed_ticks,
        "repeat_completed_ticks": second.completed_ticks,
        "reproducible": reproducible,
        "peak_abs_command_n": peak,
        "error": first.error or second.error,
        "elapsed_seconds": time.monotonic() - start,
        "nominal_reference": None
        if nominal is None
        else {
            "run_id": nominal["run_id"],
            "trace_sha256": nominal["trace_sha256"],
            "peak_abs_command_n": nominal["peak_abs_command_n"],
        },
        "trace_path": f"runs/{identity}/trace.jsonl.gz",
        "truth_path": f"runs/{identity}/truth.jsonl.gz",
    }
    temporary = Path(output) / "pending" / (identity + "-" + uuid.uuid4().hex)
    temporary.mkdir(parents=True)
    for stem, data in (("trace", first.trace), ("truth", first.truth_trace)):
        (temporary / f"{stem}.jsonl.gz").write_bytes(gzip.compress(data, compresslevel=6, mtime=0))
    (temporary / "metrics.json").write_bytes(canonical(row))
    directory.parent.mkdir(parents=True, exist_ok=True)
    temporary.rename(directory)
    return row
