"""Phase B comparisons; never change the Phase A binary64 contract."""

import argparse
import json
import math
from pathlib import Path

from tools.compare_traces import TRACE_FIELDS, TRUTH_FIELDS, read_json, read_run

CONTRACT = read_json(Path(__file__).with_name("contract.json"))


def stats(values):
    return {
        "max_absolute": max(abs(v) for v in values),
        "rms": math.sqrt(math.fsum(v * v for v in values) / len(values)),
    }


def compare(left, right, reference=False):
    left, right = Path(left), Path(right)
    a, aa = read_run(left)
    b, bb = read_run(right)
    if (a["controller"], b["controller"]) != (
        "preview" if reference else "preview_c32",
        "preview_c32",
    ):
        raise ValueError("wrong controllers for Phase B comparison")
    for key in (
        "contact_profile",
        "seed",
        "control_dt_us",
        "physics_dt_us",
        "completed_ticks",
        "duration_s",
        "verdict_contract",
    ):
        if a[key] != b[key]:
            raise ValueError(f"incompatible experiments: {key}")
    ca, cb = read_json(left / "config.json"), read_json(right / "config.json")
    pa, pb = dict(ca["parameters"]), dict(cb["parameters"])
    pa.pop("controller")
    pb.pop("controller")
    if pa != pb or any(
        ca[k] != cb[k] for k in ("contact", "mjcf_sha256", "verdict_contract_sha256")
    ):
        raise ValueError("plant/sensor/reference parameters differ")
    if not reference and any(a[k] != b[k] for k in ("source_sha256", "config_sha256")):
        raise ValueError("C32 source/config mismatch")
    same_build = not reference and a["controller_build"]["host"] == b["controller_build"]["host"]
    same_environment = same_build and a["platform_fingerprint"] == b["platform_fingerprint"]
    checks = {
        "same_verdict": a["verdict"] == b["verdict"],
        "same_safety_stop": a["safety_stop"] == b["safety_stop"],
    }
    # A float64 reference may be FAIL for another profile in later experiments;
    # no transport failure is relabeled as a task FAIL by this comparison.
    if same_environment:
        for name in ("trace_sha256", "truth_sha256"):
            checks[name] = a["determinism"][name] == b["determinism"][name]
    deltas, maxima = {}, dict.fromkeys(("position_m", "velocity_m_s", "force_n"), 0.0)
    for kind, fields in (("trace", TRACE_FIELDS), ("truth", TRUTH_FIELDS)):
        for field, unit in fields.items():
            diffs = []
            for row_a, row_b in zip(aa[kind], bb[kind], strict=True):
                x, y = row_a[field], row_b[field]
                if x is None or y is None or unit not in maxima:
                    if x != y:
                        checks["discrete_fields_equal"] = False
                else:
                    diffs.append(x - y)
            if diffs:
                summary = stats(diffs)
                deltas[f"{kind}.{field}"] = {"unit": unit, **summary}
                maxima[unit] = max(maxima[unit], summary["max_absolute"])
    limits = CONTRACT["cross_c32_strict_tolerances"]
    for unit, difference in maxima.items():
        checks[f"{unit}_within_budget"] = difference < limits[unit]
    metric_deltas = {}
    for window in ("free", "contact"):
        for key in ("rms_e_um", "peak_abs_edot_mm_s", "peak_contact_force_mn"):
            x, y = a[window][key], b[window][key]
            relative = abs(x - y) / max(abs(x), abs(y)) if x or y else 0.0
            metric_deltas[f"{window}.{key}"] = {
                "left": x,
                "right": y,
                "relative_difference": relative,
            }
            checks[f"{window}.{key}_within_budget"] = relative < limits["metric_relative"]
    if reference and b["contact_profile"] == "primary":
        expected = CONTRACT["primary_reference_contact_rms_um"]
        checks["primary_nominal_pass"] = b["verdict"]["status"] == CONTRACT["primary_task_verdict"]
        checks["primary_rms_within_preregistered_5_percent"] = (
            abs(b["contact"]["rms_e_um"] - expected) / expected
            <= CONTRACT["primary_contact_rms_relative_difference_max_inclusive"]
        )
        checks["primary_needle_difference_below_0_1_um"] = (
            deltas["truth.needle_z_m"]["max_absolute"]
            < CONTRACT["primary_max_needle_position_difference_m_strict"]
        )
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "comparison": "float64-vs-C32"
        if reference
        else "same-build-bitwise"
        if same_environment
        else "cross-C32-tolerance",
        "left_platform": a["platform_fingerprint"],
        "right_platform": b["platform_fingerprint"],
        "left_build": a.get("controller_build"),
        "right_build": b["controller_build"],
        "max_absolute_deltas": maxima,
        "per_field_deltas": deltas,
        "metric_deltas": metric_deltas,
        "trace_sha256": {
            "left": a["determinism"]["trace_sha256"],
            "right": b["determinism"]["trace_sha256"],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compare(args.left, args.right, args.reference)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {"status": "INVALID", "error": str(exc)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return {"PASS": 0, "FAIL": 1, "INVALID": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
