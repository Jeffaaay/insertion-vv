"""Measure equilibrium F/penetration using the unchanged MJCF, with motor loads."""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from .plant import MODEL_PATH


def calibrate() -> dict:
    model = mujoco.MjModel.from_xml_path(str(MODEL_PATH))
    points = []
    for load_n in (0.0008, 0.0016, 0.0032, 0.0048, 0.0064, 0.0080):
        data = mujoco.MjData(model)
        data.qpos[0] = -load_n / 16.0  # Initial guess only, never a constraint.
        data.ctrl[:] = (-load_n, 0.0)
        for _ in range(5000):
            mujoco.mj_step(model, data)
        mujoco.mj_forward(model, data)
        wrench = np.zeros(6)
        force = 0.0
        for i in range(data.ncon):
            mujoco.mj_contactForce(model, data, i, wrench)
            force += max(0.0, float(wrench[0]))
        points.append(
            {
                "applied_load_n": load_n,
                "penetration_m": float(data.qpos[1] - data.qpos[0]),
                "contact_force_n": force,
                "max_abs_velocity_m_s": float(np.max(np.abs(data.qvel))),
            }
        )
    depths = np.array([p["penetration_m"] for p in points])
    forces = np.array([p["contact_force_n"] for p in points])
    slope, intercept = np.polyfit(depths, forces, 1)
    residual = forces - (slope * depths + intercept)
    result = {
        "method": "6 constant motor loads; 5 s settling per load; linear F versus true penetration",
        "mujoco_version": mujoco.__version__,
        "solref": model.pair_solref[0].tolist(),
        "solimp": model.pair_solimp[0].tolist(),
        "measured_stiffness_n_per_m": float(slope),
        "fit_intercept_n": float(intercept),
        "fit_max_abs_residual_n": float(np.max(np.abs(residual))),
        "points": points,
    }
    result["passed"] = bool(
        15.2 <= slope <= 16.8
        and max(p["max_abs_velocity_m_s"] for p in points) < 1e-8
        and max(abs(p["contact_force_n"] - p["applied_load_n"]) for p in points) < 1e-7
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = calibrate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
