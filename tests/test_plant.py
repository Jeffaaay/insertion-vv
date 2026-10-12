import mujoco
import numpy as np
import pytest

from sim.calibrate import calibrate
from sim.config import CONTACT_TARGETS_N_PER_M, Config
from sim.contracts import Command
from sim.plant import MujocoPlant, build_model
from sim.reference import reference


def test_unknown_contact_profile_rejected():
    with pytest.raises(ValueError, match="contact_profile"):
        Config(contact_profile="missing").validate()


@pytest.mark.parametrize("profile", CONTACT_TARGETS_N_PER_M)
def test_mjcf_parameters_and_reset(profile):
    plant = MujocoPlant(Config(contact_profile=profile))
    assert plant.model.nq == 2
    assert plant.model.nu == 2
    assert plant.model.body_mass[plant.model.body("needle").id] == pytest.approx(0.001)
    assert plant.model.opt.timestep == pytest.approx(0.001)
    assert plant.model.geom_type[plant.model.geom("needle_tip").id] == mujoco.mjtGeom.mjGEOM_CAPSULE
    servo = plant.model.actuator("tissue_servo").id
    assert plant.model.actuator_gainprm[servo, 0] == 8000
    assert plant.model.actuator_biasprm[servo, 1:3] == pytest.approx([-8000, -120])
    initial = plant.sensors
    initial_truth = plant.truth()
    plant.step(Command(-0.001), 1000)
    assert plant.truth() != initial_truth
    assert plant.reset(42) == initial
    assert plant.truth() == initial_truth


@pytest.mark.parametrize("profile", CONTACT_TARGETS_N_PER_M)
def test_quasistatic_contact_stiffness(profile):
    result = calibrate(profile)
    assert result["passed"], result
    assert result["measured_stiffness_n_per_m"] == pytest.approx(
        CONTACT_TARGETS_N_PER_M[profile], rel=0.05
    )
    assert max(p["penetration_m"] for p in result["points"]) >= 899e-6


def test_diagnostic_changes_only_contact_stiffness():
    primary = build_model(Config())
    diagnostic = build_model(Config(contact_profile="paper_effective"))
    assert diagnostic.pair_solref[0, 0] / primary.pair_solref[0, 0] == pytest.approx(
        3.5 / 16, rel=0, abs=1e-15
    )
    for name in dir(primary):
        if name.startswith("__") or name == "pair_solref":
            continue
        value = getattr(primary, name)
        other = getattr(diagnostic, name)
        if isinstance(value, np.ndarray):
            np.testing.assert_array_equal(value, other, err_msg=name)
    np.testing.assert_array_equal(primary.pair_solref[:, 1], diagnostic.pair_solref[:, 1])
    assert primary.opt.timestep == diagnostic.opt.timestep


def test_servo_tracks_all_prescribed_motion_components():
    cfg = Config()
    plant = MujocoPlant(cfg)
    times, positions = [], []
    for tick in range(8000):
        plant.step(Command(0), 1000)
        if tick >= 1000:
            times.append((tick + 1) / 1000)
            positions.append(plant.truth().tissue_z_m)
    # The aligned 8000/120 servo has intentional finite lag; the old <5 um
    # ideal-servo bound no longer applies. Check each harmonic against the
    # independent mass-spring-damper frequency response, allowing 1 ms discretization.
    frequencies = [
        cfg.cardiac_frequency_hz,
        2 * cfg.cardiac_frequency_hz,
        cfg.respiratory_frequency_hz,
    ]
    amplitudes = [cfg.cardiac_amplitude_m, cfg.harmonic_amplitude_m, cfg.respiratory_amplitude_m]
    columns = [np.ones(len(times))]
    for f in frequencies:
        angle = 2 * np.pi * f * np.asarray(times)
        columns.extend([np.sin(angle), np.cos(angle)])
    coefficients = np.linalg.lstsq(np.column_stack(columns), positions, rcond=None)[0]
    for i, (frequency, amplitude) in enumerate(zip(frequencies, amplitudes, strict=True)):
        measured = complex(coefficients[1 + 2 * i], coefficients[2 + 2 * i]) / amplitude
        omega = 2 * np.pi * frequency
        analytical = 8000 / (8000 - omega**2 + 1j * 120 * omega)
        assert measured == pytest.approx(analytical, rel=0.03)


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
