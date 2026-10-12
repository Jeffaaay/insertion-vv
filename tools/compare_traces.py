"""Compare complete run artifacts across platforms using the Phase A SI tolerances.

Standard library only; independent of simulation, plotting and rendering packages.
Inputs are run directories (or trace.jsonl paths with their companion artifacts).
Use --matrix to compare all controller/profile runs in two CI artifact roots.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

TOLERANCES = {"position_m": 1e-12, "velocity_m_s": 1e-9, "force_n": 1e-12}
METRIC_RELATIVE_TOLERANCE = 1e-9
FINGERPRINT_KEYS = {"os", "arch", "python", "mujoco", "numpy"}
TRACE_FIELDS = {
    "command.force_n": "force_n",
    "sensors.needle_z_m": "position_m",
    "sensors.needle_v_m_s": "velocity_m_s",
    "sensors.surface_z_m": "position_m",
    "sensors.tick": "integer",
    "sensors.time_us": "integer",
    "sensors.surface_sample_time_us": "integer",
    "sensors.surface_sequence": "integer",
    "sensors.surface_fresh": "boolean",
}
NULLABLE_FIELDS = {
    "sensors.surface_z_m",
    "sensors.surface_sample_time_us",
    "sensors.surface_sequence",
}
TRUTH_FIELDS = {
    "tick": "integer",
    "time_us": "integer",
    "needle_z_m": "position_m",
    "tissue_z_m": "position_m",
    "reference_gap_m": "position_m",
    "e_m": "position_m",
    "needle_v_m_s": "velocity_m_s",
    "tissue_v_m_s": "velocity_m_s",
    "reference_velocity_m_s": "velocity_m_s",
    "edot_m_s": "velocity_m_s",
    "contact_force_n": "force_n",
}
WINDOW_FIELDS = {"samples", "rms_e_um", "peak_abs_edot_mm_s", "peak_contact_force_mn"}


def reject_constant(value):
    raise ValueError(f"Nonfinite JSON number: {value}")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def flatten(value, prefix=""):
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    result = {}
    for key, item in value.items():
        if "." in key:
            raise ValueError("Unexpected dotted JSON key")
        path = f"{prefix}.{key}".lstrip(".")
        if isinstance(item, dict):
            result.update(flatten(item, path))
        else:
            result[path] = item
    return result


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def read_rows(path, fields, count, dt_us, prefix):
    rows = []
    for tick, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        row = flatten(json.loads(line, parse_constant=reject_constant))
        if row.keys() != fields.keys():
            raise ValueError(f"{path}: row {tick} fields do not match the trace schema")
        for key, kind in fields.items():
            value = row[key]
            if key in NULLABLE_FIELDS and value is None:
                continue
            valid = (
                type(value) is int
                if kind == "integer"
                else type(value) is bool
                if kind == "boolean"
                else finite_number(value)
            )
            if not valid:
                raise ValueError(f"{path}: invalid {key} at row {tick}")
        if row[prefix + "tick"] != tick or row[prefix + "time_us"] != tick * dt_us:
            raise ValueError(f"{path}: missing, reordered or mis-timed row {tick}")
        rows.append(row)
    if not rows or len(rows) != count:
        raise ValueError(f"{path}: expected {count} nonempty rows, found {len(rows)}")
    return rows


def read_run(path):
    directory = path.parent if path.name == "trace.jsonl" else path
    metrics = read_json(directory / "metrics.json")
    fingerprint = metrics["platform_fingerprint"]
    if fingerprint.keys() != FINGERPRINT_KEYS or not all(
        isinstance(v, str) and v for v in fingerprint.values()
    ):
        raise ValueError(f"{directory}: incomplete platform fingerprint")
    if (
        metrics["complete"] is not True
        or metrics["determinism"]["verified"] is not True
        or metrics["verdict"]["status"] not in ("PASS", "FAIL")
        or metrics["error"] is not None
    ):
        raise ValueError(f"{directory}: incomplete, invalid or internally nondeterministic run")
    dt, count = metrics["control_dt_us"], metrics["completed_ticks"]
    if type(dt) is not int or dt <= 0 or type(count) is not int or count <= 0:
        raise ValueError(f"{directory}: invalid tick metadata")
    if count * dt != metrics["duration_s"] * 1e6:
        raise ValueError(f"{directory}: incomplete duration")
    if digest(directory / "config.json") != metrics["config_sha256"]:
        raise ValueError(f"{directory}: config hash mismatch")
    trace_hash = digest(directory / "trace.jsonl")
    det = metrics["determinism"]
    if not (
        trace_hash
        == digest(directory / "repeat_trace.jsonl")
        == det["trace_sha256"]
        == det["repeat_trace_sha256"]
    ):
        raise ValueError(f"{directory}: intra-platform trace SHA-256 mismatch")
    if digest(directory / "truth.jsonl") != det["truth_sha256"] or (
        det["truth_sha256"] != det["repeat_truth_sha256"]
    ):
        raise ValueError(f"{directory}: truth hash mismatch")
    return metrics, {
        "trace": read_rows(directory / "trace.jsonl", TRACE_FIELDS, count, dt, "sensors."),
        "truth": read_rows(directory / "truth.jsonl", TRUTH_FIELDS, count, dt, ""),
    }


def compare_runs(left, right):
    a, aa = read_run(Path(left))
    b, bb = read_run(Path(right))
    # Refuse unrelated experiments; hashes identify evidence, not numeric equivalence.
    for key in (
        "source_sha256",
        "config_sha256",
        "controller",
        "contact_profile",
        "seed",
        "control_dt_us",
        "physics_dt_us",
        "completed_ticks",
        "duration_s",
        "verdict_contract",
    ):
        if a[key] != b[key]:
            raise ValueError(f"Incompatible runs: {key} differs")
    report = {
        "status": "PASS",
        "left_platform": a["platform_fingerprint"],
        "right_platform": b["platform_fingerprint"],
        "trace_sha256": {
            "left": a["determinism"]["trace_sha256"],
            "right": b["determinism"]["trace_sha256"],
        },
        "trace_hashes_equal": a["determinism"]["trace_sha256"] == b["determinism"]["trace_sha256"],
        "strict_absolute_tolerances": TOLERANCES,
        "strict_metric_relative_tolerance": METRIC_RELATIVE_TOLERANCE,
        "max_absolute_deltas": dict.fromkeys(TOLERANCES, 0.0),
        "metrics": {},
        "mismatch_count": 0,
        "first_mismatches": [],
    }

    def mismatch(field, left_value, right_value, **details):
        report["status"] = "FAIL"
        report["mismatch_count"] += 1
        if len(report["first_mismatches"]) < 20:
            report["first_mismatches"].append(
                {"field": field, "left": left_value, "right": right_value, **details}
            )

    if a["platform_fingerprint"] == b["platform_fingerprint"]:
        for key in ("trace_sha256", "truth_sha256"):
            if a["determinism"][key] != b["determinism"][key]:
                mismatch(f"intra_platform.{key}", a["determinism"][key], b["determinism"][key])

    for kind, fields in (("trace", TRACE_FIELDS), ("truth", TRUTH_FIELDS)):
        for tick, (row_a, row_b) in enumerate(zip(aa[kind], bb[kind], strict=True)):
            for field, unit in fields.items():
                x, y = row_a[field], row_b[field]
                if x is None or y is None or unit not in TOLERANCES:
                    if x != y:
                        mismatch(f"{kind}.{field}", x, y, tick=tick)
                    continue
                delta = abs(x - y)
                if not math.isfinite(delta):
                    raise ValueError(f"Nonfinite difference at {kind}.{field}, tick {tick}")
                report["max_absolute_deltas"][unit] = max(
                    report["max_absolute_deltas"][unit], delta
                )
                if delta >= TOLERANCES[unit]:
                    mismatch(f"{kind}.{field}", x, y, tick=tick, absolute_delta=delta)
    for key in ("verdict", "safety_stop"):
        if a[key] != b[key]:
            mismatch(key, a[key], b[key])

    def metric(field, x, y):
        if not finite_number(x) or not finite_number(y) or x < 0 or y < 0:
            raise ValueError(f"Missing/nonfinite/negative metric: {field}")
        # Symmetric relative error; both zero -> 0, only one zero -> 1.
        relative = abs(x - y) / max(abs(x), abs(y)) if x or y else 0.0
        report["metrics"][field] = {"left": x, "right": y, "relative_difference": relative}
        if relative >= METRIC_RELATIVE_TOLERANCE:
            mismatch(field, x, y, relative_difference=relative)

    for window in ("free", "contact"):
        if a[window].keys() != WINDOW_FIELDS or b[window].keys() != WINDOW_FIELDS:
            raise ValueError(f"Incomplete metric schema: {window}")
        for item in sorted(WINDOW_FIELDS):
            if item == "samples":
                x, y = a[window][item], b[window][item]
                if type(x) is not int or type(y) is not int or x <= 0 or y <= 0:
                    raise ValueError(f"Invalid sample count: {window}")
                if x != y:
                    mismatch(f"{window}.samples", x, y)
            else:
                metric(f"{window}.{item}", a[window][item], b[window][item])
    for key in ("whole_run_peak_abs_edot_mm_s", "whole_run_peak_contact_force_mn"):
        metric(key, a[key], b[key])
    return report


def compare_matrix(left, right):
    a, b = read_json(left / "ci_report.json"), read_json(right / "ci_report.json")
    if a["status"] != "PASS" or b["status"] != "PASS":
        raise ValueError("Both platform CI jobs must pass before cross-platform comparison")
    for field in ("git_sha", "contact_profile_matrix", "controller_matrix"):
        if a[field] != b[field]:
            raise ValueError(f"CI artifact {field} mismatch")
    if set(a["contact_profile_matrix"]) != {"primary", "paper_effective"} or set(
        a["controller_matrix"]
    ) != {"lab_frame_pd", "delayed_feedback"}:
        raise ValueError("Expected the complete two-controller/two-profile CI matrix")
    results = {}
    for profile in a["contact_profile_matrix"]:
        for controller in a["controller_matrix"]:
            key = f"{profile}/{controller}"
            results[key] = compare_runs(left / key, right / key)
    return {
        "status": "PASS" if all(r["status"] == "PASS" for r in results.values()) else "FAIL",
        "git_sha": a["git_sha"],
        "comparisons": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = (compare_matrix if args.matrix else compare_runs)(args.left, args.right)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report = {"status": "INVALID", "error": str(exc)}
    encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return {"PASS": 0, "FAIL": 1, "INVALID": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
