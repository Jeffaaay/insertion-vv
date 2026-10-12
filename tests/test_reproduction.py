import pytest

from sim.ci import REPRODUCTION, reproduction_checks


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


def test_lab_frame_hash_regression_rejects_a_different_trace():
    metrics = {
        "controller": "lab_frame_pd",
        "contact_profile": "primary",
        "contact": {"rms_e_um": 256},
    }
    expected = REPRODUCTION["lab_frame_pd"]["trace_sha256"]["primary"]
    assert all(reproduction_checks(metrics, expected).values())
    assert not all(reproduction_checks(metrics, "0" * 64).values())
