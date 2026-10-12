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


@pytest.mark.parametrize("profile", ["primary", "paper_effective"])
@pytest.mark.parametrize(
    "contact,passes", [(19.9, False), (20.0, True), (40.0, True), (40.1, False)]
)
def test_offsetfree_contact_gate_is_registered_for_both_profiles(profile, contact, passes):
    metrics = {
        "controller": "delayed_feedback_offsetfree",
        "contact_profile": profile,
        "contact": {"rms_e_um": contact},
    }
    assert all(reproduction_checks(metrics, "unused").values()) == passes


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


@pytest.mark.parametrize(
    "rms,status,passes",
    [
        (10.0, "PASS", True),
        (10.00001, "PASS", False),
        (9.0, "FAIL", False),
        (9.0, "INVALID", False),
    ],
)
def test_preview_primary_requires_both_preregistered_rms_and_task_pass(rms, status, passes):
    metrics = {
        "controller": "preview",
        "contact_profile": "primary",
        "contact": {"rms_e_um": rms},
        "verdict": {"status": status},
    }
    assert all(reproduction_checks(metrics, "unused").values()) == passes


@pytest.mark.parametrize("status,passes", [("PASS", True), ("FAIL", True), ("INVALID", False)])
def test_preview_diagnostic_is_reported_without_primary_acceptance(status, passes):
    metrics = {
        "controller": "preview",
        "contact_profile": "paper_effective",
        "contact": {"rms_e_um": 100},
        "verdict": {"status": status},
    }
    assert all(reproduction_checks(metrics, "unused").values()) == passes


@pytest.mark.parametrize(
    "controller", ["lab_frame_pd", "delayed_feedback", "delayed_feedback_offsetfree"]
)
def test_all_previous_controller_hashes_are_registered_for_both_platforms(controller):
    for baseline in REPRODUCTION[controller]["platform_baselines"]:
        assert (
            reference_trace_hashes(baseline["platform_fingerprint"], controller)
            == baseline["trace_sha256"]
        )
        assert set(baseline["trace_sha256"]) == {"primary", "paper_effective"}
        unknown = dict(baseline["platform_fingerprint"], python="unregistered")
        assert reference_trace_hashes(unknown, controller) is None


def test_extended_metadata_does_not_disable_old_controller_regression_anchors():
    baseline = REPRODUCTION["lab_frame_pd"]["platform_baselines"][0]
    extended = dict(baseline["platform_fingerprint"], cpu_model="extra runtime provenance")
    assert reference_trace_hashes(extended) == baseline["trace_sha256"]
