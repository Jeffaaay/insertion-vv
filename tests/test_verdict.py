import math

import pytest

from sim.metrics import verdict, window_metrics


@pytest.mark.parametrize(
    "rms,velocity,stop,complete,reproducible,expected",
    [
        (19.999, 1.999, False, True, True, "PASS"),
        (20, 1, False, True, True, "FAIL"),
        (10, 2, False, True, True, "FAIL"),
        (10, 1, True, True, True, "FAIL"),
        (30, 3, False, False, True, "INVALID"),
        (10, 1, False, True, False, "INVALID"),
        (math.nan, 1, False, True, True, "INVALID"),
        (10, math.inf, False, True, True, "INVALID"),
        (None, 1, False, True, True, "INVALID"),
    ],
)
def test_contract(rms, velocity, stop, complete, reproducible, expected):
    result = verdict(
        {
            "samples": 5000,
            "rms_e_um": rms,
            "peak_abs_edot_mm_s": velocity,
            "peak_contact_force_mn": 1,
        },
        complete=complete,
        reproducible=reproducible,
        safety_stop=stop,
    )
    assert result["status"] == expected


def test_empty_window_is_invalid():
    contact = window_metrics([], 3_000_000, 8_000_000)
    assert (
        verdict(contact, complete=True, reproducible=True, safety_stop=False)["status"] == "INVALID"
    )


def test_window_boundaries_and_true_velocity():
    rows = [
        {"time_us": t, "e_m": e, "edot_m_s": v, "contact_force_n": f}
        for t, e, v, f in [
            (2_999_000, 100, 100, 100),
            (3_000_000, 3e-6, -0.001, 0.001),
            (7_999_000, 4e-6, 0.002, 0.002),
            (8_000_000, 100, 100, 100),
        ]
    ]
    result = window_metrics(rows, 3_000_000, 8_000_000)
    assert result["samples"] == 2
    assert result["rms_e_um"] == pytest.approx(math.sqrt(12.5))
    assert result["peak_abs_edot_mm_s"] == pytest.approx(2)
    assert result["peak_contact_force_mn"] == pytest.approx(2)
