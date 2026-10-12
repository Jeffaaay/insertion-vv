import math
from dataclasses import replace

import numpy as np
import pytest

from sim.config import Config
from sim.contracts import Sensors
from sim.controllers import DelayedFeedback
from sim.preview import HarmonicSurfaceEstimator, PreviewFeedback


def estimator():
    cfg = Config()
    return HarmonicSurfaceEstimator(
        cfg.preview_frequencies_hz,
        cfg.preview_delay_us,
        cfg.preview_initial_std_m,
        cfg.preview_measurement_std_m,
        cfg.preview_process_std_m_sqrt_s,
    )


def frame(sampled, value, *, now=None, sequence=None):
    return Sensors(
        (sampled + 15000) // 1000,
        sampled + 15000 if now is None else now,
        0.001,
        0.0,
        value,
        sampled,
        sampled // 1000 if sequence is None else sequence,
        True,
    )


def signal(time_s):
    # Deliberately different amplitudes, phases and DC from the simulator.
    terms = ((1.2, 137e-6, 0.7), (2.4, 43e-6, -0.4), (0.25, 219e-6, 1.1))
    position, velocity = -37e-6, 0.0
    for frequency, amplitude, phase in terms:
        omega = 2 * math.pi * frequency
        position += amplitude * math.sin(omega * time_s + phase)
        velocity += omega * amplitude * math.cos(omega * time_s + phase)
    return position, velocity


def test_no_surface_knowledge_before_first_delivered_frame():
    e = estimator()
    assert e.estimate(frame(0, 100e-6, now=14999)) == (0.0, 0.0)
    assert np.count_nonzero(e._state) == 0
    assert e.estimate(frame(0, 100e-6)) != (0.0, 0.0)


@pytest.mark.parametrize("spacing,drop_every", [(1000, None), (40000, 4)])
def test_learns_unknown_amplitudes_phases_and_previews_position_and_velocity(spacing, drop_every):
    e = estimator()
    for index, sampled in enumerate(range(0, 6_000_001, spacing)):
        if drop_every and index % drop_every == 0:
            continue
        e.estimate(frame(sampled, signal(sampled * 1e-6)[0], sequence=index))
    before_state, before_covariance = e._state.copy(), e._covariance.copy()
    for now in (6_015_000, 6_027_000, 6_055_000):
        position, velocity = e.estimate(Sensors(0, now, 999, 999, None, None, None, False))
        expected = signal(now * 1e-6)
        assert position == pytest.approx(expected[0], abs=1e-6)
        assert velocity == pytest.approx(expected[1], abs=1e-5)
    # Output propagation must not advance/filter a held measurement a second time.
    np.testing.assert_array_equal(e._state, before_state)
    np.testing.assert_array_equal(e._covariance, before_covariance)
    assert np.linalg.eigvalsh(e._covariance).min() >= -1e-24


@pytest.mark.parametrize("kind", ["held", "duplicate", "old", "future", "premature", "nan"])
def test_invalid_frames_cannot_correct_the_filter(kind):
    a, b = estimator(), estimator()
    for sampled in (0, 1000, 2000):
        f = frame(sampled, sampled * 1e-9)
        assert a.estimate(f) == b.estimate(f)
    held = replace(f, time_us=18_000, surface_fresh=False)
    corrupt = replace(held, surface_z_m=100.0)
    if kind == "duplicate":
        corrupt = replace(corrupt, surface_fresh=True)
    elif kind == "old":
        corrupt = replace(
            corrupt, surface_fresh=True, surface_sample_time_us=1000, surface_sequence=1
        )
    elif kind in ("future", "premature"):
        corrupt = replace(
            corrupt,
            surface_fresh=True,
            surface_sample_time_us=(19000 if kind == "future" else 4000),
            surface_sequence=19,
        )
    elif kind == "nan":
        corrupt = frame(3000, float("nan"))
    assert a.estimate(held) == b.estimate(corrupt)
    np.testing.assert_array_equal(a._covariance, b._covariance)


def test_first_measurement_at_late_capture_is_not_assumed_to_be_at_zero():
    early, late = estimator(), estimator()
    assert early.estimate(frame(0, 100e-6)) == late.estimate(frame(5_000_000, 100e-6))


def test_square_root_filter_matches_covariance_kalman_equations():
    # Independent, well-conditioned covariance calculation checks both prediction
    # and measurement correction, including process noise and nonzero prior state.
    e = estimator()
    rng = np.random.default_rng(74)
    matrix = rng.normal(size=(7, 7)) * 1e-6
    covariance = matrix @ matrix.T + np.eye(7) * 1e-12
    state = rng.normal(size=7) * 50e-6
    e._covariance_root = np.linalg.cholesky(covariance)
    e._state = state.copy()
    e._sample_time_us, e._sequence = 0, 0
    transition = e.transition(40000)
    predicted = transition @ state
    covariance = transition @ covariance @ transition.T + np.eye(7) * e.process_std_m_sqrt_s**2 * 0.04
    h, variance = e._position_row, e.measurement_std_m**2
    gain = covariance @ h / (h @ covariance @ h + variance)
    expected_state = predicted + gain * (83e-6 - h @ predicted)
    residual = np.eye(7) - np.outer(gain, h)
    expected_covariance = residual @ covariance @ residual.T + np.outer(gain, gain) * variance
    e.estimate(frame(40000, 83e-6))
    np.testing.assert_allclose(e._state, expected_state, rtol=1e-13, atol=1e-19)
    np.testing.assert_allclose(e._covariance, expected_covariance, rtol=1e-13, atol=1e-26)


def test_preview_keeps_pd_arithmetic_and_does_not_refilter_estimated_velocity():
    class FixedEstimate:
        def estimate(self, sensors):
            return 123e-6, 0.0013

    baseline = DelayedFeedback(10, 0.2, 0.001, 0.0005, 0.0003, 5000)
    baseline._surface_z, baseline._surface_v = 123e-6, 0.0013
    preview = PreviewFeedback(10, 0.2, 0.001, 0.0005, 0.0003, 5000, FixedEstimate())
    f = Sensors(4000, 4_000_000, -0.0002, 0.0007, None, None, None, False)
    assert preview.command(f) == baseline.command(f)


@pytest.mark.parametrize(
    "field,value",
    [
        ("preview_initial_std_m", 0),
        ("preview_measurement_std_m", 0),
        ("preview_process_std_m_sqrt_s", -1),
        ("preview_measurement_std_m", float("nan")),
        ("preview_frequencies_hz", (1.2, 2.5, 0.25)),
        ("preview_delay_us", 0),
    ],
)
def test_invalid_preview_config_is_rejected(field, value):
    with pytest.raises(ValueError):
        replace(Config(controller="preview"), **{field: value}).validate()
