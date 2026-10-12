import numpy as np
import pytest

from sim.calibrate import calibrate
from sim.config import Config, tissue_target
from sim.contracts import Command
from sim.plant import MujocoPlant
from sim.reference import reference


def test_mjcf_parameters_and_reset():
    plant = MujocoPlant(Config())
    assert plant.model.nq == 2
    assert plant.model.nu == 2
    assert plant.model.body_mass[plant.model.body("needle").id] == pytest.approx(0.001)
    assert plant.model.opt.timestep == pytest.approx(0.001)
    initial = plant.sensors
    initial_truth = plant.truth()
    plant.step(Command(-0.001), 1000)
    assert plant.truth() != initial_truth
    assert plant.reset(42) == initial
    assert plant.truth() == initial_truth


def test_quasistatic_contact_stiffness():
    result = calibrate()
    assert result["passed"], result
    assert result["measured_stiffness_n_per_m"] == pytest.approx(16, rel=0.05)


def test_servo_tracks_all_prescribed_motion_components():
    cfg = Config()
    plant = MujocoPlant(cfg)
    errors = []
    for tick in range(8000):
        plant.step(Command(0), 1000)
        if tick >= 1000:
            errors.append(plant.truth().tissue_z_m - tissue_target((tick + 1) / 1000, cfg))
    assert np.sqrt(np.mean(np.square(errors))) < 5e-6


def test_substeps_and_bad_step():
    plant = MujocoPlant(Config(physics_dt_us=500))
    plant.step(Command(0), 1000)
    assert plant.data.time == pytest.approx(0.001)
    with pytest.raises(ValueError):
        plant.step(Command(0), 500)
    with pytest.raises(ValueError):
        plant.step(Command(float("nan")), 1000)


def test_task_schedule():
    args = (0.001, 0.0005, 0.0003)
    assert reference(0, *args) == (0.001, 0)
    assert reference(1_000_000, *args) == (0.0005, 0)
    assert reference(2_000_000, *args) == (0.0005, 0)
    assert reference(2_500_000, *args) == (-0.0003, 0)
    assert reference(8_000_000, *args) == (-0.0003, 0)
    assert reference(2_250_000, *args)[0] == pytest.approx(0.0001)
