"""Registered capture/transport faults; same JSON-subset YAML and tables as Rust."""

import json
import math
from collections import deque
from pathlib import Path

import numpy as np

from sim.contracts import Sensors

ROOT = Path(__file__).resolve().parents[1]
ABLATIONS = (
    "baseline",
    "no-delay",
    "no-jitter-model",
    "no-quantization",
    "no-noise",
    "no-dropped-frame-model",
)


def definitions():
    return {f"F{i}": json.loads((ROOT / f"faults/F{i}.yaml").read_text()) for i in range(1, 9)}


class FaultInjector:
    def __init__(self, cfg, case, tables=None):
        self.cfg, self.case = cfg, case
        self.fault = case["fault"]
        self.level = case["level"]
        self.onset = case["onset_ms"]
        self.ablation = case["ablation"]
        if self.ablation not in ABLATIONS:
            raise ValueError("unregistered ablation")
        if self.fault != "none":
            spec = definitions()[self.fault]
            if self.onset not in spec["onsets_ms"] or case["seed"] not in spec["seeds"]:
                raise ValueError("unregistered onset or seed")
            if self.level not in spec["levels"]:
                raise ValueError("unregistered fault severity")
        if cfg.seed != case["seed"]:
            raise ValueError("config/scenario seed mismatch")
        self.tables = tables or json.loads((ROOT / "faults/random-v1.json").read_text())
        self.rng = np.random.Generator(np.random.PCG64(cfg.seed))
        self.pending = deque()
        self.last = None
        self.sequence = 0
        self.frozen_value = None
        self.previous_capture = None
        self.last_due = -1

    def active(self, tick):
        if self.fault == "none" or tick < self.onset:
            return False
        if self.fault in ("F1", "F6"):
            return tick < self.onset + self.level
        if self.fault in ("F2", "F3"):
            return tick < self.onset + 300
        return True

    def skip(self, tick):
        return self.fault == "F6" and self.active(tick)

    def clip(self, tick, force, nominal_peak):
        if self.fault == "F7" and self.active(tick):
            if nominal_peak is None or not math.isfinite(nominal_peak):
                raise ValueError("F7 requires registered nominal reference")
            limit = nominal_peak * (self.level / 100)
            return max(-limit, min(limit, force))
        return force

    def capture(self, tick, measured):
        """Accept a full-rate measured sample and return latest delivered metadata."""
        previous = self.previous_capture
        self.previous_capture = measured
        active = self.active(tick)
        seq = self.sequence
        self.sequence += 1
        drop = False
        base = 0 if self.ablation == "no-delay" else 15
        delay = base
        if active:
            if self.fault == "F1":
                if self.frozen_value is None:
                    if previous is None:
                        raise ValueError("F1 needs a pre-onset captured sample")
                    self.frozen_value = previous
                measured = self.frozen_value
            elif self.fault == "F2" and self.ablation != "no-dropped-frame-model":
                word = self.tables["F2"][str(self.cfg.seed)][tick - self.onset]
                drop = word < math.floor(self.level * 2**32 / 100)
            elif self.fault == "F3" and self.ablation != "no-jitter-model":
                key = str(self.level) if self.level == 0.5 else str(int(self.level))
                delay = self.tables["F3"][str(self.cfg.seed)][str(base)][key][tick - self.onset]
            elif self.fault == "F4":
                drop = tick % (1000 // self.level) != 0
            elif self.fault == "F8" and self.ablation != "no-quantization":
                half = 2 ** (self.level - 1)
                lsb = 0.002 / 2**self.level
                measured = max(-half, min(half - 1, round(measured / lsb))) * lsb
        if not drop:
            due = max(tick + delay, self.last_due)
            self.last_due = due
            self.pending.append((due, tick * 1000, seq, measured))
        fresh = False
        while self.pending and self.pending[0][0] <= tick:
            _, sampled, seq, value = self.pending.popleft()
            self.last = (sampled, seq, value)
            fresh = True
        return (*self.last, fresh) if self.last is not None else (None, None, None, False)

    def read(self, tick, needle_z, needle_v, surface_z):
        # Preserve the frozen sensor RNG's draws, including zero noise/dropout.
        dropped = self.rng.random() < self.cfg.surface_dropout_probability
        measured = surface_z + self.rng.normal(0, self.cfg.surface_noise_std_m)
        if dropped:
            raise ValueError("C1 registration has zero nominal dropout")
        sampled, seq, value, fresh = self.capture(tick, measured)
        return Sensors(tick, tick * 1000, needle_z, needle_v, value, sampled, seq, fresh)
