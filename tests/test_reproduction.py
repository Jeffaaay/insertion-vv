import pytest

from sim.ci import REPRODUCTION, reference_trace_hashes, reproduction_checks


@pytest.mark.parametrize("free,contact", [(14.9, 175), (25.1, 175), (20, 149.9), (20, 200.1)])
def test_delayed_primary_reproduction_gate_rejects_out_of_range_results(free, contact):
    metrics = {
        "controller": "delayed_feedback",
        "contact_profile": "primary",
        "free": {"rms_e_um": free},
        "contact": {"rms_e_um": contact},
    }
    assert not all(reproduction_checks(metrics, "unused").values())


def test_diagnostic_contact_is_not_constrained_to_primary_paper_range():
    metrics = {
        "controller": "delayed_feedback",
        "contact_profile": "paper_effective",
        "free": {"rms_e_um": 20},
        "contact": {"rms_e_um": 78},
    }
    assert all(reproduction_checks(metrics, "unused").values())


@pytest.mark.parametrize("baseline", REPRODUCTION["lab_frame_pd"]["platform_baselines"])
def test_lab_frame_hash_regression_rejects_a_different_trace(baseline):
    metrics = {
        "controller": "lab_frame_pd",
        "contact_profile": "primary",
        "contact": {"rms_e_um": 256},
        "platform_fingerprint": baseline["platform_fingerprint"],
    }
    expected = baseline["trace_sha256"]["primary"]
    assert all(reproduction_checks(metrics, expected).values())
    assert not all(reproduction_checks(metrics, "0" * 64).values())


@pytest.mark.parametrize("field", ["os", "arch", "python", "mujoco", "numpy"])
def test_historical_hash_is_never_applied_to_a_different_fingerprint(field):
    fingerprint = dict(
        REPRODUCTION["lab_frame_pd"]["platform_baselines"][0]["platform_fingerprint"]
    )
    fingerprint[field] = "unregistered"
    assert reference_trace_hashes(fingerprint) is None
