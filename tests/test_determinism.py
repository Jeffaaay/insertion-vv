import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sim.config import CONTACT_TARGETS_N_PER_M, CONTROLLERS

REPO = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("profile", CONTACT_TARGETS_N_PER_M)
@pytest.mark.parametrize("controller", CONTROLLERS)
def test_independent_process_trace_sha_and_optional_truth(tmp_path, profile, controller):
    # No display server, renderer, or shared process/RNG state is required.
    env = dict(os.environ)
    env.pop("DISPLAY", None)
    outputs = []
    for name, extra in (("a", []), ("b", ["--no-truth"])):
        output = tmp_path / name
        subprocess.run(
            [
                sys.executable,
                "-m",
                "sim.run",
                "--controller",
                controller,
                "--contact-profile",
                profile,
                "--output",
                str(output),
                "--seed",
                "917",
                "--sample-hz",
                "25",
                "--noise-std-m",
                "0.000002",
                "--dropout-probability",
                "0.1",
                *extra,
            ],
            cwd=REPO,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        metrics = json.loads((output / "metrics.json").read_text())
        assert metrics["complete"]
        assert metrics["contact_profile"] == profile
        assert metrics["controller"] == controller
        assert metrics["determinism"]["verified"]
        assert metrics["verdict"]["status"] != "INVALID"
        assert digest(output / "trace.jsonl") == digest(output / "repeat_trace.jsonl")
        assert digest(output / "trace.jsonl") == metrics["determinism"]["trace_sha256"]
        assert len((output / "wall_time.csv").read_text().splitlines()) == 8001
        outputs.append(output)
    assert digest(outputs[0] / "trace.jsonl") == digest(outputs[1] / "trace.jsonl")
    assert (outputs[0] / "truth.jsonl").exists()
    assert not (outputs[1] / "truth.jsonl").exists()
    assert b"wall_time" not in (outputs[0] / "trace.jsonl").read_bytes()
