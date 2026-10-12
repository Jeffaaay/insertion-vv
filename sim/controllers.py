"""Phase A controllers receive Sensors, never Truth or plant parameters."""

from dataclasses import dataclass, field

from .contracts import Command, Sensors
from .reference import reference


@dataclass(frozen=True, slots=True)
class LabFramePD:
    kp: float
    kd: float
    initial_height: float
    hover_height: float
    insertion_depth: float

    def command(self, sensors: Sensors) -> Command:
        z_ref, v_ref = reference(
            sensors.time_us, self.initial_height, self.hover_height, self.insertion_depth
        )
        return Command(
            self.kp * (z_ref - sensors.needle_z_m) + self.kd * (v_ref - sensors.needle_v_m_s)
        )


@dataclass(slots=True)
class DelayedFeedback:
    kp: float
    kd: float
    initial_height: float
    hover_height: float
    insertion_depth: float
    velocity_filter_tau_us: int
    _surface_z: float = field(default=0.0, init=False)
    _surface_v: float = field(default=0.0, init=False)
    _sample_time_us: int | None = field(default=None, init=False)
    _sequence: int | None = field(default=None, init=False)

    def command(self, sensors: Sensors) -> Command:
        sampled = sensors.surface_sample_time_us
        sequence = sensors.surface_sequence
        if (
            sensors.surface_fresh
            and sensors.surface_z_m is not None
            and sampled is not None
            and sequence is not None
            and sampled <= sensors.time_us
            and (self._sample_time_us is None or sampled > self._sample_time_us)
            and (self._sequence is None or sequence > self._sequence)
        ):
            if self._sample_time_us is not None:
                # Use capture spacing, including lost frames, not arrival/tick spacing.
                elapsed_us = sampled - self._sample_time_us
                measured_v = (sensors.surface_z_m - self._surface_z) / (elapsed_us * 1e-6)
                alpha = elapsed_us / (self.velocity_filter_tau_us + elapsed_us)
                self._surface_v += alpha * (measured_v - self._surface_v)
            self._surface_z = sensors.surface_z_m
            self._sample_time_us = sampled
            self._sequence = sequence

        gap_ref, gap_v_ref = reference(
            sensors.time_us, self.initial_height, self.hover_height, self.insertion_depth
        )
        # Hold the last delayed measurement; never advance position by velocity * age.
        # Before any frame arrives, the nominal surface/velocity are both zero.
        return Command(
            self.kp * (gap_ref + self._surface_z - sensors.needle_z_m)
            + self.kd * (gap_v_ref + self._surface_v - sensors.needle_v_m_s)
        )


@dataclass(slots=True)
class AccelerationBiasObserver:
    """Paper V, Eq. (8): position-only predict/correct, with commanded input."""

    mass_kg: float
    dt_s: float
    gain_position: float
    gain_velocity: float
    gain_acceleration: float
    _position: float | None = field(default=None, init=False)
    _velocity: float = field(default=0.0, init=False)
    _acceleration_bias: float = field(default=0.0, init=False)

    def update(self, position_m: float, previous_command_n: float) -> float:
        if self._position is None:
            # Known rest startup; do not fabricate a pre-start interval or read truth.
            self._position = position_m
            return self._acceleration_bias
        predicted_position = self._position + self.dt_s * self._velocity
        predicted_velocity = self._velocity + self.dt_s * (
            self._acceleration_bias + previous_command_n / self.mass_kg
        )
        innovation = position_m - predicted_position
        self._position = predicted_position + self.gain_position * innovation
        self._velocity = predicted_velocity + self.gain_velocity * innovation
        self._acceleration_bias += self.gain_acceleration * innovation
        return self._acceleration_bias


@dataclass(slots=True)
class DelayedFeedbackOffsetFree:
    feedback: DelayedFeedback
    observer: AccelerationBiasObserver
    _previous_command_n: float = field(default=0.0, init=False)

    def command(self, sensors: Sensors) -> Command:
        bias = self.observer.update(sensors.needle_z_m, self._previous_command_n)
        feedback_command = self.feedback.command(sensors)
        # Only added term: cancel inferred acceleration, not a measured contact force.
        force = feedback_command.force_n - self.observer.mass_kg * bias
        self._previous_command_n = force
        return Command(force)
