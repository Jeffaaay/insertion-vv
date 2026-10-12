from dataclasses import replace

import pytest

from sim.config import Config
from sim.sensors import SensorModel


def frames(cfg, ticks=100):
    model = SensorModel(cfg)
    return [model.read(i, 1, 2, i * 1e-6) for i in range(ticks)]


def test_exact_15_ms_delay_and_initial_missing_frame():
    result = frames(Config())
    assert all(r.surface_z_m is None for r in result[:15])
    assert result[15].surface_sample_time_us == 0
    assert result[15].surface_z_m == 0
    assert result[20].surface_z_m == pytest.approx(5e-6)
    assert result[20].needle_z_m == 1  # Local encoder has no surface-sensor delay.
    assert result[20].surface_sequence == 5


def test_25_hz_sampling_and_hold():
    result = frames(Config(surface_sample_hz=25))
    assert [r.tick for r in result if r.surface_fresh] == [15, 55, 95]
    assert all(r.surface_sequence == 0 for r in result[15:55])
    assert result[55].surface_sample_time_us == 40_000


def test_total_dropout_does_not_invent_measurements():
    assert all(r.surface_z_m is None for r in frames(Config(surface_dropout_probability=1)))


def test_seed_controls_noise_and_drops():
    cfg = Config(surface_noise_std_m=2e-6, surface_dropout_probability=0.2)
    assert frames(cfg) == frames(cfg)
    assert frames(cfg) != frames(replace(cfg, seed=43))


@pytest.mark.parametrize(
    "changes",
    [
        {"controller": "preview"},
        {"delayed_kp_n_per_m": 0},
        {"delayed_kd_ns_per_m": -1},
        {"surface_velocity_filter_tau_us": 0},
        {"surface_sample_hz": 30},
        {"surface_delay_us": -1},
        {"surface_delay_us": 15001},
        {"surface_noise_std_m": -1},
        {"surface_dropout_probability": 1.1},
        {"physics_dt_us": 600},
        {"duration_us": 7_000_000},
        {"seed": -1},
    ],
)
def test_invalid_config(changes):
    with pytest.raises(ValueError):
        Config(**changes).validate()
