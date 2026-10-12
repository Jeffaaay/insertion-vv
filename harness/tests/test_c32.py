import ctypes as ct
import os
from dataclasses import fields, replace
from pathlib import Path

import pytest

from harness.c32 import ControllerC32, Input, input_value
from harness.run import capture
from sim.config import Config
from sim.contracts import Sensors


@pytest.fixture
def controller():
    directory = os.environ.get("C32_BUILD")
    if not directory:
        pytest.fail("C32_BUILD must point to the verified build directory")
    return ControllerC32(Path(directory))


def test_complete_sensor_boundary():
    sensors = Sensors(16, 16000, 0.0012, -0.0002, 0.0003, 1000, 1, True)
    value = input_value(sensors)
    assert (value.tick, value.time_us, value.sample_time_us, value.sequence, value.flags) == (
        16,
        16000,
        1000,
        1,
        3,
    )
    assert value.needle_position == ct.c_float(sensors.needle_z_m).value
    assert value.needle_velocity == ct.c_float(sensors.needle_v_m_s).value
    assert value.surface_position == ct.c_float(sensors.surface_z_m).value
    assert set(f.name for f in fields(Sensors)) == {
        "tick",
        "time_us",
        "needle_z_m",
        "needle_v_m_s",
        "surface_z_m",
        "surface_sample_time_us",
        "surface_sequence",
        "surface_fresh",
    }
    assert ct.sizeof(Input) == 32


def test_missing_input_does_not_fabricate_measurement():
    value = input_value(Sensors(0, 0, 0.001, 0, None, None, None, False))
    assert value.flags == 0 and value.surface_position == 0
    assert value.sample_time_us == value.sequence == 0


def test_u32_overflow_rejected():
    with pytest.raises(ValueError, match="u32"):
        input_value(Sensors(2**32, 0, 0.001, 0, None, None, None, False))


def test_parameters_match_frozen_python_when_quantized(controller):
    cfg = Config(controller="preview")
    expected = {
        "kp": cfg.delayed_kp_n_per_m,
        "kd": cfg.delayed_kd_ns_per_m,
        "mass": cfg.observer_mass_kg,
        "observer_position": cfg.observer_gain_position,
        "observer_velocity": cfg.observer_gain_velocity,
        "observer_acceleration": cfg.observer_gain_acceleration,
        "initial_height": cfg.initial_height_m,
        "hover_height": cfg.hover_height_m,
        "depth": cfg.insertion_depth_m,
        "initial_std": cfg.preview_initial_std_m,
        "measurement_std": cfg.preview_measurement_std_m,
        "process_std": cfg.preview_process_std_m_sqrt_s,
    }
    actual = controller.parameter_values()
    for key, value in expected.items():
        assert actual[key] == ct.c_float(value).value
    assert actual["frequencies"] == [ct.c_float(v).value for v in cfg.preview_frequencies_hz]
    assert actual["dt_us"] == cfg.control_dt_us and actual["delay_us"] == cfg.preview_delay_us


def test_invalid_tick_and_reset(controller):
    sensors = Sensors(0, 0, 0.001, 0, None, None, None, False)
    initial = controller.command(sensors)
    with pytest.raises(ValueError, match="tick"):
        controller.command(sensors)
    controller.reset()
    assert controller.command(sensors) == initial
    with pytest.raises(ValueError):
        controller.command(replace(sensors, tick=1, time_us=1000, needle_z_m=float("nan")))


def test_truth_output_has_no_effect(controller):
    cfg = Config(controller="preview")
    with_truth = capture(cfg, controller, write_truth=True)
    without_truth = capture(cfg, controller, write_truth=False)
    assert with_truth.complete and without_truth.complete
    assert with_truth.trace == without_truth.trace
    assert with_truth.rows == without_truth.rows
    assert with_truth.truth_trace and not without_truth.truth_trace
