"""Measure equilibrium F/penetration using the unchanged MJCF, with motor loads."""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from .config import CONTACT_TARGETS_N_PER_M, Config
from .plant import build_model, contact_parameters


def calibrate(contact_profile: str = "primary") -> dict:
    model = build_model(Config(contact_profile=contact_profile))
    target = CONTACT_TARGETS_N_PER_M[contact_profile]
    points = []
    # Match the physical depth range across profiles, including trajectory peaks.
    # Targets choose loads and initial guesses only; position is never constrained.
    for depth_um in (50, 100, 200, 300, 400, 500, 750, 900):
        load_n = target * depth_um * 1e-6
        data = mujoco.MjData(model)
        data.qpos[0] = -depth_um * 1e-6
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
        "method": "8 constant motor loads; 5 s each; 50-900 um target range; fit F vs true depth",
        "mujoco_version": mujoco.__version__,
        **contact_parameters(model, contact_profile),
        "measured_stiffness_n_per_m": float(slope),
        "fit_intercept_n": float(intercept),
        "fit_max_abs_residual_n": float(np.max(np.abs(residual))),
        "points": points,
    }
    result["passed"] = bool(
        0.95 * target <= slope <= 1.05 * target
        and max(p["max_abs_velocity_m_s"] for p in points) < 1e-8
        and max(abs(p["contact_force_n"] - p["applied_load_n"]) for p in points) < 1e-7
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contact-profile", choices=CONTACT_TARGETS_N_PER_M, default="primary")
    args = parser.parse_args()
    result = calibrate(args.contact_profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
