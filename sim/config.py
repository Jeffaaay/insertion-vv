"""Versioned experiment inputs; all physical quantities use SI units."""

import math
from dataclasses import asdict, dataclass

CONTACT_TARGETS_N_PER_M = {"primary": 16.0, "paper_effective": 3.5}
CONTROLLERS = ("lab_frame_pd", "delayed_feedback", "delayed_feedback_offsetfree", "preview")


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
    delayed_kp_n_per_m: float = 10.0
    delayed_kd_ns_per_m: float = 0.2
    surface_velocity_filter_tau_us: int = 5000
    observer_mass_kg: float = 0.001
    observer_gain_position: float = 0.6
    observer_gain_velocity: float = 12.0
    observer_gain_acceleration: float = 400.0
    preview_frequencies_hz: tuple[float, ...] = (1.2, 2.4, 0.25)
    preview_delay_us: int = 15_000
    preview_initial_std_m: float = 500e-6
    preview_measurement_std_m: float = 2e-6
    preview_process_std_m_sqrt_s: float = 0.2e-6

    def validate(self) -> None:
        if self.contact_profile not in CONTACT_TARGETS_N_PER_M:
            raise ValueError("contact_profile must be primary or paper_effective")
        if self.controller not in CONTROLLERS:
            raise ValueError(f"controller must be one of {CONTROLLERS}")
        if self.preview_frequencies_hz != (1.2, 2.4, 0.25) or self.preview_delay_us != 15_000:
            raise ValueError(
                "Step 2 preview fixes frequencies at 1.2/2.4/0.25 Hz and delay at 15 ms"
            )
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
        if self.surface_velocity_filter_tau_us <= 0:
            raise ValueError("surface velocity filter time constant must be positive")
        if not 0 <= self.surface_dropout_probability <= 1:
            raise ValueError("dropout probability must be in [0, 1]")
        for key, value in asdict(self).items():
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"{key} must be finite")
        if (
            min(self.preview_initial_std_m, self.preview_measurement_std_m) <= 0
            or self.preview_process_std_m_sqrt_s < 0
        ):
            raise ValueError(
                "Kalman initial/measurement variance must be positive; process nonnegative"
            )
        if (
            min(
                self.observer_mass_kg,
                self.observer_gain_position,
                self.observer_gain_velocity,
                self.observer_gain_acceleration,
            )
            <= 0
        ):
            raise ValueError("observer mass and gains must be positive")
        if (
            self.surface_noise_std_m < 0
            or min(
                self.kp_n_per_m,
                self.kd_ns_per_m,
                self.delayed_kp_n_per_m,
                self.delayed_kd_ns_per_m,
            )
            <= 0
        ):
            raise ValueError("noise must be nonnegative and PD gains positive")


def tissue_target(time_s: float, cfg: Config) -> float:
    return (
        cfg.cardiac_amplitude_m * math.sin(2 * math.pi * cfg.cardiac_frequency_hz * time_s)
        + cfg.harmonic_amplitude_m
        * math.sin(4 * math.pi * cfg.cardiac_frequency_hz * time_s + cfg.harmonic_phase_rad)
        + cfg.respiratory_amplitude_m
        * math.sin(2 * math.pi * cfg.respiratory_frequency_hz * time_s)
    )
