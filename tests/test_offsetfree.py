from dataclasses import replace

import pytest

from sim.config import Config
from sim.contracts import Sensors
from sim.controllers import AccelerationBiasObserver, DelayedFeedback, DelayedFeedbackOffsetFree


def observer():
    return AccelerationBiasObserver(0.001, 0.001, 0.6, 12.0, 400.0)


def feedback():
    return DelayedFeedback(10, 0.2, 0.001, 0.0005, 0.0003, 5000)


def test_observer_initializes_at_measured_position_without_startup_impulse():
    o = observer()
    assert o.update(0.001, 0.0) == 0.0
    for _ in range(100):
        assert o.update(0.001, 0.0) == 0.0


@pytest.mark.parametrize("bias", [-2.0, 0.0, 2.0])
def test_observer_identifies_unknown_acceleration_separately_from_command(bias):
    # Independent Euler plant: hidden bias is never passed to the observer.
    # Changing commanded acceleration must not be mistaken for a disturbance.
    o = observer()
    position, velocity, command = 0.001, 0.0, 0.0
    estimate = o.update(position, command)
    for tick in range(3000):
        command = 0.0003 if (tick // 137) % 2 else -0.0002
        position, velocity = (
            position + 0.001 * velocity,
            velocity + 0.001 * (command / 0.001 + bias),
        )
        estimate = o.update(position, command)
    assert estimate == pytest.approx(bias, abs=1e-6)


def test_zero_bias_cancellation_preserves_original_controller_bitwise():
    baseline = feedback()
    zero_bias = observer()
    zero_bias.gain_acceleration = 0.0  # Test-only ablation; not a supported run config.
    added = DelayedFeedbackOffsetFree(feedback(), zero_bias)
    for tick in range(100):
        sample_tick = max(0, tick - 15)
        frame = Sensors(
            tick,
            tick * 1000,
            0.001 - tick * 1e-7,
            -0.0001,
            sample_tick * 2e-7 if tick >= 15 else None,
            sample_tick * 1000 if tick >= 15 else None,
            sample_tick if tick >= 15 else None,
            tick >= 15 and tick % 7 != 0,
        )
        assert added.command(frame) == baseline.command(frame)


def test_cancellation_uses_prior_total_command_and_current_encoder_only():
    class RecordingObserver:
        mass_kg = 0.001

        def __init__(self):
            self.calls = []

        def update(self, position, previous_command):
            self.calls.append((position, previous_command))
            return 2.0  # Known positive disturbance; cancel with negative force.

    o = RecordingObserver()
    c = DelayedFeedbackOffsetFree(feedback(), o)
    frame = Sensors(3000, 3_000_000, -0.0003, 0.0, None, None, None, False)
    first = c.command(frame)
    assert first.force_n == pytest.approx(-0.002)
    c.command(replace(frame, tick=3001, time_us=3_001_000))
    assert o.calls == [(-0.0003, 0.0), (-0.0003, first.force_n)]


@pytest.mark.parametrize("kind", ["held", "duplicate", "old", "future"])
def test_offsetfree_does_not_predict_or_accept_invalid_surface_frames(kind):
    a = DelayedFeedbackOffsetFree(feedback(), observer())
    b = DelayedFeedbackOffsetFree(feedback(), observer())
    first = Sensors(3000, 3_000_000, -0.0003, 0, 0, 2_985_000, 2985, True)
    second = replace(
        first,
        tick=3001,
        time_us=3_001_000,
        surface_z_m=1e-6,
        surface_sample_time_us=2_986_000,
        surface_sequence=2986,
    )
    for frame in (first, second):
        assert a.command(frame) == b.command(frame)
    held = replace(second, tick=3002, time_us=3_002_000, surface_fresh=False)
    invalid = replace(held, surface_z_m=999.0)
    if kind == "duplicate":
        invalid = replace(invalid, surface_fresh=True)
    elif kind == "old":
        invalid = replace(
            invalid, surface_fresh=True, surface_sample_time_us=2_984_000, surface_sequence=2984
        )
    elif kind == "future":
        invalid = replace(
            invalid, surface_fresh=True, surface_sample_time_us=3_003_000, surface_sequence=3003
        )
    assert a.command(held) == b.command(invalid)
    assert a.feedback._surface_z == 1e-6


@pytest.mark.parametrize(
    "field",
    [
        "observer_mass_kg",
        "observer_gain_position",
        "observer_gain_velocity",
        "observer_gain_acceleration",
    ],
)
@pytest.mark.parametrize("value", [0.0, -1.0, float("nan")])
def test_invalid_observer_configuration_is_rejected(field, value):
    with pytest.raises(ValueError):
        replace(Config(controller="delayed_feedback_offsetfree"), **{field: value}).validate()
