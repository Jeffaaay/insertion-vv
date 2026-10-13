"""New plant extension for registered phase-continuous cardiac drift only."""

import math

import mujoco
import numpy as np

from sim.config import tissue_target
from sim.plant import MujocoPlant

from .faults import FaultInjector


def drifting_target(t, cfg, target):
    if t < 2:
        return tissue_target(t, cfg)
    delta = target - cfg.cardiac_frequency_hz
    if t <= 5:
        cycles = cfg.cardiac_frequency_hz * t + 0.5 * delta * (t - 2) ** 2 / 3
    else:
        cycles = cfg.cardiac_frequency_hz * 5 + 1.5 * delta + target * (t - 5)
    phase = 2 * math.pi * cycles
    return (
        cfg.cardiac_amplitude_m * math.sin(phase)
        + cfg.harmonic_amplitude_m * math.sin(2 * phase + cfg.harmonic_phase_rad)
        + cfg.respiratory_amplitude_m * math.sin(2 * math.pi * cfg.respiratory_frequency_hz * t)
    )


class FaultPlant(MujocoPlant):
    def __init__(self, cfg, case):
        self.case = case
        super().__init__(cfg)

    def reset(self, seed):
        self.injector = FaultInjector(self.cfg, self.case)
        return super().reset(seed)

    def _observe(self):
        return self.injector.read(
            self.tick, float(self.data.qpos[0]), float(self.data.qvel[0]), float(self.data.qpos[1])
        )

    def step(self, cmd, dt_us):
        if self.case["fault"] != "F5" or self.tick < 2000:
            return super().step(cmd, dt_us)
        if dt_us != self.cfg.control_dt_us or not np.isfinite(cmd.force_n):
            raise ValueError("invalid plant command/timestep")
        self.data.ctrl[0] = cmd.force_n
        for _ in range(dt_us // self.cfg.physics_dt_us):
            t = self.physics_tick * self.cfg.physics_dt_us / 1e6
            self.data.ctrl[1] = drifting_target(t, self.cfg, self.case["level"])
            mujoco.mj_step(self.model, self.data)
            self.physics_tick += 1
        self.tick += 1
        mujoco.mj_forward(self.model, self.data)
        self.sensors = self._observe()
        return self.sensors
