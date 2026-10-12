"""MuJoCo backend. Truth is confined to the plant/evaluation side."""

from dataclasses import dataclass
from pathlib import Path

import mujoco
import numpy as np

from .config import Config, tissue_target
from .contracts import Command, Sensors
from .sensors import SensorModel

MODEL_PATH = Path(__file__).with_name("plant.xml")


@dataclass(frozen=True, slots=True)
class Truth:
    needle_z_m: float
    needle_v_m_s: float
    tissue_z_m: float
    tissue_v_m_s: float
    contact_force_n: float


class MujocoPlant:
    def __init__(self, cfg: Config):
        cfg.validate()
        self.cfg = cfg
        self.model = mujoco.MjModel.from_xml_path(str(MODEL_PATH))
        self.model.opt.timestep = cfg.physics_dt_us / 1e6
        self.data = mujoco.MjData(self.model)
        self.reset(cfg.seed)

    def reset(self, seed: int) -> Sensors:
        from dataclasses import replace

        cfg = replace(self.cfg, seed=seed)
        cfg.validate()
        mujoco.mj_resetData(self.model, self.data)
        self.tick = 0
        self.physics_tick = 0
        self.data.qpos[:] = (cfg.initial_height_m, tissue_target(0, cfg))
        self.data.ctrl[1] = tissue_target(0, cfg)
        self.sensor_model = SensorModel(cfg)
        mujoco.mj_forward(self.model, self.data)
        self.sensors = self._observe()
        return self.sensors

    def _observe(self) -> Sensors:
        return self.sensor_model.read(
            self.tick,
            float(self.data.qpos[0]),
            float(self.data.qvel[0]),
            float(self.data.qpos[1]),
        )

    def step(self, cmd: Command, dt_us: int) -> Sensors:
        if dt_us != self.cfg.control_dt_us:
            raise ValueError("step must advance exactly one configured control tick")
        if not np.isfinite(cmd.force_n):
            raise ValueError("nonfinite actuator command")
        self.data.ctrl[0] = cmd.force_n
        for _ in range(dt_us // self.cfg.physics_dt_us):
            # Integer time avoids accumulating waveform phase roundoff.
            t = self.physics_tick * self.cfg.physics_dt_us / 1e6
            self.data.ctrl[1] = tissue_target(t, self.cfg)
            mujoco.mj_step(self.model, self.data)
            self.physics_tick += 1
        self.tick += 1
        # Refresh contacts/forces at the same time as qpos/qvel, with held controls.
        mujoco.mj_forward(self.model, self.data)
        self.sensors = self._observe()
        return self.sensors

    def truth(self) -> Truth:
        contact_force = 0.0
        wrench = np.zeros(6)
        for i in range(self.data.ncon):
            mujoco.mj_contactForce(self.model, self.data, i, wrench)
            contact_force += max(0.0, float(wrench[0]))
        return Truth(
            float(self.data.qpos[0]),
            float(self.data.qvel[0]),
            float(self.data.qpos[1]),
            float(self.data.qvel[1]),
            contact_force,
        )

    def healthy(self) -> bool:
        return bool(
            np.all(np.isfinite(self.data.qpos))
            and np.all(np.isfinite(self.data.qvel))
            and not any(w.number for w in self.data.warning)
        )
