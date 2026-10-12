"""Versioned experiment inputs; all physical quantities use SI units."""

import math
from dataclasses import asdict, dataclass

CONTACT_TARGETS_N_PER_M = {"primary": 16.0, "paper_effective": 3.5}


@dataclass(frozen=True)
class Config:
    controller: str = "lab_frame_pd"
    contact_profile: str = "primary"
    seed: int = 42
    control_dt_us: int = 1000
    physics_dt_us: int = 1000
    duration_us: int = 8_000_000
    cardiac_amplitude_m: float = 200e-6
    cardiac_frequency_hz: float = 1.2
    harmonic_amplitude_m: float = 60e-6
    harmonic_phase_rad: float = 0.0
    respiratory_amplitude_m: float = 300e-6
    respiratory_frequency_hz: float = 0.25
    initial_height_m: float = 1e-3
    hover_height_m: float = 0.5e-3
    insertion_depth_m: float = 0.3e-3
    surface_delay_us: int = 15_000
    surface_sample_hz: int = 1000
    surface_noise_std_m: float = 0.0
    surface_dropout_probability: float = 0.0
    kp_n_per_m: float = 400.0
    kd_ns_per_m: float = 0.8

    def validate(self) -> None:
        if self.contact_profile not in CONTACT_TARGETS_N_PER_M:
            raise ValueError("contact_profile must be primary or paper_effective")
        if self.controller != "lab_frame_pd":
            raise ValueError("Only lab_frame_pd is implemented; CI determinism gates expansion")
        if not 0 <= self.seed < 2**64:
            raise ValueError("seed must fit u64")
        if self.control_dt_us != 1000:
            raise ValueError("Phase A control tick is fixed at 1 ms")
        if self.physics_dt_us <= 0 or self.control_dt_us % self.physics_dt_us:
            raise ValueError("physics timestep must divide the control tick")
        if self.duration_us != 8_000_000:
            raise ValueError("A valid benchmark must cover the full 8-second timeline")
        if self.surface_sample_hz not in (25, 1000):
            raise ValueError("surface_sample_hz must be 25 or 1000")
        if self.surface_delay_us < 0 or self.surface_delay_us % self.control_dt_us:
            raise ValueError("surface delay must be a nonnegative whole number of ticks")
        if not 0 <= self.surface_dropout_probability <= 1:
            raise ValueError("dropout probability must be in [0, 1]")
        for key, value in asdict(self).items():
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"{key} must be finite")
        if self.surface_noise_std_m < 0 or self.kp_n_per_m <= 0 or self.kd_ns_per_m <= 0:
            raise ValueError("noise must be nonnegative and PD gains positive")


def tissue_target(time_s: float, cfg: Config) -> float:
    return (
        cfg.cardiac_amplitude_m * math.sin(2 * math.pi * cfg.cardiac_frequency_hz * time_s)
        + cfg.harmonic_amplitude_m
        * math.sin(4 * math.pi * cfg.cardiac_frequency_hz * time_s + cfg.harmonic_phase_rad)
        + cfg.respiratory_amplitude_m
        * math.sin(2 * math.pi * cfg.respiratory_frequency_hz * time_s)
    )
