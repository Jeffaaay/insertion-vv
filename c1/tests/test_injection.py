import json
import os
import struct
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from c1.faults import ROOT, FaultInjector, definitions
from c1.plant import drifting_target
from c1.runner import execute, scenario
from sim.config import Config, tissue_target
from sim.run import simulate
from sim.sensors import SensorModel


def test_f1_single_tick_and_window_boundaries():
    f = FaultInjector(Config(), scenario(fault="F1", level=1, onset_ms=200))
    observed = [f.capture(t, float(t)) for t in range(230)]
    assert observed[214] == (199000, 199, 199.0, True)
    assert observed[215] == (200000, 200, 199.0, True)
    assert observed[216] == (201000, 201, 201.0, True)


def test_f4_matches_legacy_sampling_except_sequence():
    f = FaultInjector(Config(), scenario(fault="F4", level=25, onset_ms=0))
    old = SensorModel(replace(Config(), surface_sample_hz=25))
    for tick in range(160):
        a = f.read(tick, 0.0, 0.0, tick * 1e-6)
        b = old.read(tick, 0.0, 0.0, tick * 1e-6)
        assert (a.surface_z_m, a.surface_sample_time_us, a.surface_fresh) == (
            b.surface_z_m,
            b.surface_sample_time_us,
            b.surface_fresh,
        )


def test_quantizer_is_not_an_identity_and_saturates():
    f = FaultInjector(Config(), scenario(fault="F8", level=10, onset_ms=0, ablation="no-delay"))
    assert f.capture(0, 0.01)[2] == 511 * (0.002 / 1024)
    assert f.capture(1, -0.01)[2] == -0.001
    lsb = 0.002 / 1024
    assert f.capture(2, 2.5 * lsb)[2] == 2 * lsb


def test_f6_skip_window_and_f7_clip():
    f = FaultInjector(Config(), scenario(fault="F6", level=5, onset_ms=200))
    assert [t for t in range(199, 207) if f.skip(t)] == list(range(200, 205))
    f = FaultInjector(Config(), scenario(fault="F7", level=25, onset_ms=200))
    assert f.clip(199, 3.0, 2.0) == 3.0
    assert f.clip(200, 3.0, 2.0) == 0.5
    assert f.clip(200, -3.0, 2.0) == -0.5


def test_drift_continuity_and_unchanged_prefix():
    cfg = Config()
    for t in (0, 0.5, 1.999):
        assert drifting_target(t, cfg, 1.8) == tissue_target(t, cfg)
    for boundary in (2.0, 5.0):
        assert (
            abs(
                drifting_target(boundary + 1e-7, cfg, 1.8)
                - drifting_target(boundary - 1e-7, cfg, 1.8)
            )
            < 1e-9
        )


@pytest.fixture(scope="module")
def legacy_preview():
    return simulate(Config(controller="preview"))


def test_nominal_is_bitwise_legacy(legacy_preview):
    current, _ = execute(scenario())
    assert current.complete
    assert current.trace == legacy_preview.trace
    assert current.truth_trace == legacy_preview.truth_trace


def test_seeded_repeat_and_ablation_identities(legacy_preview):
    case = scenario(fault="F2", level=50, onset_ms=2400, seed=44)
    first, _ = execute(case)
    repeat, _ = execute(case)
    no_noise, _ = execute({**case, "ablation": "no-noise"})
    disabled, _ = execute({**case, "ablation": "no-dropped-frame-model"})
    assert first.complete and repeat.complete
    assert first.trace == repeat.trace == no_noise.trace
    assert first.truth_trace == repeat.truth_trace == no_noise.truth_trace
    assert disabled.trace == legacy_preview.trace
    assert disabled.truth_trace == legacy_preview.truth_trace


def test_f7_full_scale_is_identity(legacy_preview):
    peak = max(
        abs(json.loads(line)["command"]["force_n"]) for line in legacy_preview.trace.splitlines()
    )
    current, _ = execute(scenario(fault="F7", level=100, onset_ms=2400), nominal_peak=peak)
    assert current.trace == legacy_preview.trace
    assert current.truth_trace == legacy_preview.truth_trace


def test_c32_nominal_and_tick_gap():
    from harness.c32 import ControllerC32
    from harness.run import capture

    build = os.environ.get("C1_BUILD")
    if not build:
        pytest.skip("set C1_BUILD for frozen C32 ABI checks")
    legacy = capture(Config(controller="preview"), ControllerC32(Path(build)))
    current, _ = execute(scenario(controller="preview_c32"), build)
    assert current.trace == legacy.trace and current.truth_trace == legacy.truth_trace
    current, _ = execute(
        scenario(controller="preview_c32", fault="F6", level=1, onset_ms=200), build
    )
    assert not current.complete
    assert current.completed_ticks == 201
    assert "rejected tick 201" in current.error


def test_python_rust_binary_equivalence(tmp_path, legacy_preview):
    binary = os.environ.get("C1_RUST")
    if not binary:
        pytest.skip("set C1_RUST for independent cross-language acceptance")
    samples = [r["tissue_z_m"] for r in legacy_preview.rows]
    # Include actual drifting-plant samples in F5, not just a synthetic waveform.
    drift, _ = execute(scenario(fault="F5", level=1.8, onset_ms=2000))
    drift_samples = [r["tissue_z_m"] for r in drift.rows]
    for fault, spec in definitions().items():
        for ablation in ("baseline", "no-delay"):
            case = scenario(
                fault=fault,
                level=spec["levels"][-1],
                onset_ms=2000 if fault == "F5" else 200,
                ablation=ablation,
            )
            values = drift_samples if fault == "F5" else samples
            case_path, input_path, output_path = (
                tmp_path / n for n in ("case.json", "input.bin", "output.bin")
            )
            case_path.write_text(json.dumps(case))
            input_path.write_bytes(
                b"".join(
                    struct.pack("<dd", value, (i % 9 - 4) * 0.6) for i, value in enumerate(values)
                )
            )
            subprocess.run(
                [binary, str(ROOT), str(case_path), str(input_path), str(output_path)], check=True
            )
            f = FaultInjector(Config(), case)
            expected = bytearray()
            for i, value in enumerate(values):
                sampled, seq, val, fresh = f.capture(i, value)
                expected.extend(
                    struct.pack(
                        "<qqdBBd",
                        -1 if sampled is None else sampled,
                        -1 if seq is None else seq,
                        0.0 if val is None else val,
                        fresh,
                        f.skip(i),
                        f.clip(i, (i % 9 - 4) * 0.6, 2.0),
                    )
                )
            assert output_path.read_bytes() == expected, (fault, ablation)
