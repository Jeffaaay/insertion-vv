"""Controller-facing capabilities. No simulator, evaluator, or Truth imports."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Sensors:
    tick: int
    time_us: int
    needle_z_m: float
    needle_v_m_s: float
    surface_z_m: float | None
    surface_sample_time_us: int | None
    surface_sequence: int | None
    surface_fresh: bool


@dataclass(frozen=True, slots=True)
class Command:
    force_n: float
