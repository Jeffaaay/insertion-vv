from dataclasses import replace

import pytest

from sim.config import Config
from sim.contracts import Sensors
from sim.controllers import DelayedFeedback
from sim.sensors import SensorModel


def controller():
    return DelayedFeedback(10, 0.2, 0.001, 0.0005, 0.0003, 5000)


def frame(sampled, position, *, now=None, sequence=None, fresh=True):
    return Sensors(
        0,
        sampled + 15_000 if now is None else now,
        -0.0003,
        0.0,
        position,
        sampled,
        sampled // 1000 if sequence is None else sequence,
        fresh,
    )


def test_only_arrived_measurements_can_change_the_command():
    sensor = SensorModel(Config())
    changed_sensor = SensorModel(Config())
    baseline, changed = controller(), controller()
    for tick in range(16):
        a = sensor.read(tick, 0.001, 0, 0)
        b = changed_sensor.read(tick, 0.001, 0, 0.0001)
        if tick < 15:
            assert baseline.command(a) == changed.command(b)
        else:
            assert changed.command(b).force_n - baseline.command(a).force_n == pytest.approx(0.001)


def test_first_frame_initializes_without_a_velocity_spike():
    observed = controller().command(frame(3_000_000, 0.0001))
    assert observed.force_n == pytest.approx(0.001)


def test_velocity_filter_uses_sample_spacing_across_missing_frames():
    c = controller()
    c.command(frame(3_000_000, 0))
    # Captures are 40 ms apart, even if delivery intervals change. True secant = 1 mm/s.
    cmd = c.command(frame(3_040_000, 40e-6, now=3_100_000))
    assert cmd.force_n == pytest.approx(10 * 40e-6 + 0.2 * (40 / 45) * 0.001)


@pytest.mark.parametrize("kind", ["held", "duplicate", "old", "future"])
def test_old_missing_or_invalid_frames_do_not_extrapolate_position(kind):
    c = controller()
    c.command(frame(3_000_000, 0))
    arrived = frame(3_001_000, 1e-6)
    previous = c.command(arrived)
    if kind == "held":
        changed = replace(arrived, time_us=4_000_000, surface_fresh=False)
    elif kind == "duplicate":
        changed = replace(arrived, time_us=4_000_000, surface_z_m=1.0)
    elif kind == "old":
        changed = frame(2_999_000, 1.0, now=4_000_000)
    else:
        changed = frame(5_000_000, 1.0, now=4_000_000)
    assert c.command(changed) == previous


def test_filter_suppresses_alternating_measurement_noise():
    c = controller()
    c.command(frame(3_000_000, 1e-6))
    for i in range(1, 100):
        position = (-1) ** i * 1e-6
        cmd = c.command(frame(3_000_000 + i * 1000, position))
        if i > 50:
            # Raw derivative alternates at 2 mm/s; filtered rate must be below 0.25 mm/s.
            assert abs((cmd.force_n - 10 * position) / 0.2) < 0.00025


def test_new_controller_has_no_state_from_previous_run():
    used = controller()
    used.command(frame(3_000_000, 0.01))
    no_frame = Sensors(4000, 4_000_000, -0.0003, 0, None, None, None, False)
    assert controller().command(no_frame).force_n == 0.0
    assert used.command(no_frame).force_n != 0.0
