import copy
import hashlib
import json
import math

import pytest

from tools.compare_traces import compare_matrix, compare_runs


def save_json(path, value):
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def save_run(path, *, trace=None, truth=None, change_metrics=None, system="Linux"):
    """Small complete evidence bundle; no renderer or simulation dependency."""
    path.mkdir(exist_ok=True)
    if trace is None:
        trace = [
            {
                "sensors": {
                    "tick": 0,
                    "time_us": 0,
                    "needle_z_m": 0.0,
                    "needle_v_m_s": 0.0,
                    "surface_z_m": None,
                    "surface_sample_time_us": None,
                    "surface_sequence": None,
                    "surface_fresh": False,
                },
                "command": {"force_n": 0.0},
            }
        ]
    if truth is None:
        truth = [
            {
                "tick": 0,
                "time_us": 0,
                "needle_z_m": 0.0,
                "needle_v_m_s": 0.0,
                "tissue_z_m": 0.0,
                "tissue_v_m_s": 0.0,
                "contact_force_n": 0.0,
                "reference_gap_m": 0.0,
                "reference_velocity_m_s": 0.0,
                "e_m": 0.0,
                "edot_m_s": 0.0,
            }
        ]
    trace_bytes = "".join(json.dumps(r) + "\n" for r in trace).encode()
    truth_bytes = "".join(json.dumps(r) + "\n" for r in truth).encode()
    (path / "trace.jsonl").write_bytes(trace_bytes)
    (path / "repeat_trace.jsonl").write_bytes(trace_bytes)
    (path / "truth.jsonl").write_bytes(truth_bytes)
    (path / "config.json").write_bytes(b"{}\n")

    def sha(data):
        return hashlib.sha256(data).hexdigest()

    window = {
        "samples": 1,
        "rms_e_um": 200.0,
        "peak_abs_edot_mm_s": 1.0,
        "peak_contact_force_mn": 2.0,
    }
    metrics = {
        "platform_fingerprint": {
            "os": system,
            "arch": "x86_64",
            "python": "3.12.10",
            "mujoco": "3.8.0",
            "numpy": "2.2.6",
        },
        "source_sha256": "test-source",
        "config_sha256": sha(b"{}\n"),
        "controller": "lab_frame_pd",
        "contact_profile": "primary",
        "seed": 42,
        "control_dt_us": 1000,
        "physics_dt_us": 1000,
        "completed_ticks": 1,
        "duration_s": 0.001,
        "complete": True,
        "safety_stop": False,
        "error": None,
        "verdict_contract": {"position_rms_limit_um": 20},
        "verdict": {"status": "FAIL", "reasons": ["contact_rms_e_um >= 20"]},
        "free": copy.deepcopy(window),
        "contact": copy.deepcopy(window),
        "whole_run_peak_abs_edot_mm_s": 1.0,
        "whole_run_peak_contact_force_mn": 2.0,
        "wall_time_us": {"mean": 30.0},
        "run_id": system,
        "determinism": {
            "verified": True,
            "trace_sha256": sha(trace_bytes),
            "repeat_trace_sha256": sha(trace_bytes),
            "truth_sha256": sha(truth_bytes),
            "repeat_truth_sha256": sha(truth_bytes),
        },
    }
    if change_metrics:
        change_metrics(metrics)
    save_json(path / "metrics.json", metrics)
    return trace, truth


@pytest.fixture
def pair(tmp_path):
    left, right = tmp_path / "linux", tmp_path / "windows"
    save_run(left)
    save_run(right, system="Windows")
    return left, right


@pytest.mark.parametrize(
    "field,limit",
    [
        ("needle_z_m", 1e-12),
        ("needle_v_m_s", 1e-9),
        ("contact_force_n", 1e-12),
    ],
)
@pytest.mark.parametrize("at_boundary", [False, True])
def test_strict_si_tolerance_boundaries(pair, field, limit, at_boundary):
    left, right = pair
    trace, truth = save_run(right, system="Windows")
    truth[0][field] = limit if at_boundary else math.nextafter(limit, 0)
    save_run(right, trace=trace, truth=truth, system="Windows")
    result = compare_runs(left, right)
    assert result["status"] == ("FAIL" if at_boundary else "PASS")


def test_cross_platform_last_ulp_passes_despite_different_hashes_and_timing(pair):
    left, right = pair
    trace, truth = save_run(left)
    trace[0]["sensors"]["surface_z_m"] = 0.0002174455954359589
    save_run(left, trace=trace, truth=truth)
    trace[0]["sensors"]["surface_z_m"] = 0.00021744559543595892
    save_run(
        right,
        trace=trace,
        truth=truth,
        system="Windows",
        change_metrics=lambda m: m["wall_time_us"].update(mean=9999),
    )
    result = compare_runs(left / "trace.jsonl", right / "trace.jsonl")
    assert result["status"] == "PASS"
    assert not result["trace_hashes_equal"]
    assert result["max_absolute_deltas"]["position_m"] == 2.710505431213761e-20


def test_same_fingerprint_cannot_use_tolerance_to_bypass_bitwise_equality(pair):
    left, right = pair
    trace, truth = save_run(right)
    trace[0]["command"]["force_n"] = 1e-20
    save_run(right, trace=trace, truth=truth)
    assert compare_runs(left, right)["status"] == "FAIL"


@pytest.mark.parametrize("delta,passes", [(1e-7, True), (1e-6, False)])
def test_metric_relative_tolerance(pair, delta, passes):
    left, right = pair
    save_run(
        right, system="Windows", change_metrics=lambda m: m["contact"].update(rms_e_um=200 + delta)
    )
    assert (compare_runs(left, right)["status"] == "PASS") == passes


@pytest.mark.parametrize("right_value,passes", [(0.0, True), (1e-30, False)])
def test_zero_metric_has_explicit_relative_error_semantics(pair, right_value, passes):
    left, right = pair
    save_run(left, change_metrics=lambda m: m["free"].update(peak_contact_force_mn=0))
    save_run(
        right,
        system="Windows",
        change_metrics=lambda m: m["free"].update(peak_contact_force_mn=right_value),
    )
    assert (compare_runs(left, right)["status"] == "PASS") == passes


def test_identical_numbers_do_not_hide_verdict_mismatch(pair):
    left, right = pair
    save_run(
        right,
        system="Windows",
        change_metrics=lambda m: m.update(verdict={"status": "PASS", "reasons": []}),
    )
    assert compare_runs(left, right)["status"] == "FAIL"


@pytest.mark.parametrize("mutation", ["timestamp", "missing_field", "nan", "infinity", "empty"])
def test_invalid_trace_cannot_pass_tolerance_comparison(pair, mutation):
    left, right = pair
    trace, truth = save_run(right, system="Windows")
    if mutation == "timestamp":
        trace[0]["sensors"]["time_us"] = 1
    elif mutation == "missing_field":
        del trace[0]["command"]["force_n"]
    elif mutation in ("nan", "infinity"):
        trace[0]["command"]["force_n"] = float(mutation)
    else:
        trace = []
    save_run(right, trace=trace, truth=truth, system="Windows")
    with pytest.raises(ValueError):
        compare_runs(left, right)


@pytest.mark.parametrize(
    "file", ["trace.jsonl", "repeat_trace.jsonl", "truth.jsonl", "config.json"]
)
def test_corrupt_artifact_hash_is_rejected(pair, file):
    left, right = pair
    with (right / file).open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(ValueError):
        compare_runs(left, right)


def test_exact_sensor_discrete_fields_are_not_tolerance_compared(pair):
    left, right = pair
    trace, truth = save_run(right, system="Windows")
    trace[0]["sensors"]["surface_fresh"] = True
    save_run(right, trace=trace, truth=truth, system="Windows")
    assert compare_runs(left, right)["status"] == "FAIL"


def test_different_config_cannot_be_compared(pair):
    left, right = pair
    save_run(right, system="Windows", change_metrics=lambda m: m.update(seed=43))
    with pytest.raises(ValueError, match="seed"):
        compare_runs(left, right)


def test_matrix_checks_every_case_and_requires_complete_artifacts(tmp_path):
    left, right = tmp_path / "linux", tmp_path / "windows"
    for root, system in ((left, "Linux"), (right, "Windows")):
        root.mkdir()
        save_json(
            root / "ci_report.json",
            {
                "status": "PASS",
                "git_sha": "same-commit",
                "contact_profile_matrix": ["primary", "paper_effective"],
                "controller_matrix": [
                    "lab_frame_pd",
                    "delayed_feedback",
                    "delayed_feedback_offsetfree",
                ],
            },
        )
        for profile in ("primary", "paper_effective"):
            (root / profile).mkdir()
            for controller in ("lab_frame_pd", "delayed_feedback", "delayed_feedback_offsetfree"):
                save_run(
                    root / profile / controller,
                    system=system,
                    change_metrics=lambda m, p=profile, c=controller: m.update(
                        contact_profile=p, controller=c
                    ),
                )
    result = compare_matrix(left, right)
    assert result["status"] == "PASS" and len(result["comparisons"]) == 6
    target = right / "paper_effective/delayed_feedback_offsetfree"
    save_run(
        target,
        system="Windows",
        change_metrics=lambda m: m.update(
            contact_profile="paper_effective",
            controller="delayed_feedback_offsetfree",
            verdict={"status": "PASS", "reasons": []},
        ),
    )
    assert compare_matrix(left, right)["status"] == "FAIL"
    (target / "truth.jsonl").unlink()
    with pytest.raises(OSError):
        compare_matrix(left, right)
