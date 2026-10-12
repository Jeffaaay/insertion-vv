import json

import pytest

from sim.ci import reproduction_checks
from sim.config import CONTACT_TARGETS_N_PER_M, CONTROLLERS, Config
from sim.metrics import CONTRACT, window_metrics
from sim.plant import MujocoPlant
from sim.run import run, sha256, simulate


@pytest.mark.parametrize("profile", CONTACT_TARGETS_N_PER_M)
@pytest.mark.parametrize("controller", CONTROLLERS)
def test_baseline_regression_and_true_velocity(profile, controller):
    execution = simulate(Config(contact_profile=profile, controller=controller))
    assert execution.complete
    assert execution.completed_ticks == 8000
    assert not execution.safety_stop
    contact = window_metrics(execution.rows, *CONTRACT["contact_window_us"])
    assert all(
        reproduction_checks(
            {
                "controller": controller,
                "contact_profile": profile,
                "contact": contact,
                "free": window_metrics(execution.rows, *CONTRACT["free_window_us"]),
            },
            sha256(execution.trace),
        ).values()
    )
    assert contact["samples"] == 5000
    for row in execution.rows:
        assert row["edot_m_s"] == pytest.approx(
            row["reference_velocity_m_s"] - row["needle_v_m_s"] + row["tissue_v_m_s"],
            rel=0,
            abs=1e-17,
        )


def test_incomplete_run_serializes_invalid_and_preserves_evidence(monkeypatch, tmp_path):
    original = MujocoPlant.step

    def fail(self, command, dt_us):
        if self.tick == 123:
            raise RuntimeError("injected test-only early termination")
        return original(self, command, dt_us)

    monkeypatch.setattr(MujocoPlant, "step", fail)
    metrics = run(Config(), tmp_path / "partial")
    assert metrics["verdict"]["status"] == "INVALID"
    assert metrics["completed_ticks"] == 123
    assert not metrics["determinism"]["verified"]
    saved = json.loads((tmp_path / "partial" / "metrics.json").read_text())
    assert saved == metrics


def test_mismatched_repeat_is_invalid(monkeypatch, tmp_path):
    import sim.run as runner

    calls = 0

    def mismatch(cfg, *, write_truth):
        nonlocal calls
        execution = simulate(cfg, write_truth=write_truth)
        calls += 1
        if calls == 2:
            execution.trace += b"corrupted repeat\n"
        return execution

    monkeypatch.setattr(runner, "simulate", mismatch)
    metrics = run(Config(), tmp_path / "mismatch")
    assert metrics["complete"]
    assert not metrics["determinism"]["verified"]
    assert metrics["verdict"]["status"] == "INVALID"


@pytest.mark.parametrize("write_truth", [True, False])
def test_nonfinite_truth_is_invalid_even_without_truth_file(monkeypatch, tmp_path, write_truth):
    from dataclasses import replace

    original = MujocoPlant.truth

    def nonfinite(self):
        return replace(original(self), contact_force_n=float("nan"))

    monkeypatch.setattr(MujocoPlant, "truth", nonfinite)
    metrics = run(Config(), tmp_path / "nonfinite", write_truth=write_truth)
    assert metrics["verdict"]["status"] == "INVALID"
    assert metrics["completed_ticks"] == 0
