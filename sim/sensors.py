"""Delayed surface sensor and synchronous local encoder, with seeded corruption."""

from collections import deque

import numpy as np

from .config import Config
from .contracts import Sensors


class SensorModel:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.rng = np.random.Generator(np.random.PCG64(cfg.seed))
        self.pending: deque[tuple[int, int, int, float]] = deque()
        self.last: tuple[int, int, float] | None = None
        self.sequence = 0

    def read(self, tick: int, needle_z: float, needle_v: float, surface_z: float) -> Sensors:
        time_us = tick * self.cfg.control_dt_us
        period_us = 1_000_000 // self.cfg.surface_sample_hz
        if time_us % period_us == 0:
            seq = self.sequence
            self.sequence += 1
            # Always consume both draws; one stream, deterministic for a given config.
            dropped = self.rng.random() < self.cfg.surface_dropout_probability
            measured = surface_z + self.rng.normal(0, self.cfg.surface_noise_std_m)
            if not dropped:
                self.pending.append((time_us + self.cfg.surface_delay_us, time_us, seq, measured))
        fresh = False
        while self.pending and self.pending[0][0] <= time_us:
            _, sampled, seq, value = self.pending.popleft()
            self.last = (sampled, seq, value)
            fresh = True
        sampled, seq, value = self.last if self.last is not None else (None, None, None)
        return Sensors(tick, time_us, needle_z, needle_v, value, sampled, seq, fresh)
