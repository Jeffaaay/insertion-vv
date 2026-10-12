"""Measured-surface harmonic Kalman filter; no plant or evaluator capability."""

import math
from dataclasses import dataclass, field

import numpy as np

from .contracts import Command, Sensors
from .controllers import DelayedFeedback
from .reference import reference


@dataclass(slots=True)
class HarmonicSurfaceEstimator:
    frequencies_hz: tuple[float, ...]
    delay_us: int
    initial_std_m: float
    measurement_std_m: float
    process_std_m_sqrt_s: float
    _state: np.ndarray = field(init=False)
    _covariance_root: np.ndarray = field(init=False)
    _identity: np.ndarray = field(init=False)
    _position_row: np.ndarray = field(init=False)
    _velocity_row: np.ndarray = field(init=False)
    _sample_time_us: int | None = field(default=None, init=False)
    _sequence: int | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        # DC plus three rotating quadrature pairs, all in metres. No known amplitudes/phases.
        size = 1 + 2 * len(self.frequencies_hz)
        self._identity = np.eye(size)
        self._state = np.zeros(size)
        self._covariance_root = self._identity * self.initial_std_m
        self._position_row = np.zeros(size)
        self._position_row[0] = 1.0
        self._position_row[1::2] = 1.0
        self._velocity_row = np.zeros(size)
        self._velocity_row[2::2] = [2 * math.pi * f for f in self.frequencies_hz]

    @property
    def _covariance(self) -> np.ndarray:
        # Diagnostic view only; filtering never reconstructs or subtracts P.
        return self._covariance_root @ self._covariance_root.T

    @staticmethod
    def _lower_root(array: np.ndarray) -> np.ndarray:
        # QR(A.T) gives L=R.T with L L.T = A A.T, without squaring
        # the condition number. Signs of the triangular diagonal are immaterial.
        return np.linalg.qr(array.T, mode="r").T

    def transition(self, elapsed_us: int) -> np.ndarray:
        matrix = self._identity.copy()
        for i, frequency in enumerate(self.frequencies_hz):
            phase = 2 * math.pi * frequency * (elapsed_us * 1e-6)
            cosine, sine = math.cos(phase), math.sin(phase)
            j = 1 + 2 * i
            matrix[j : j + 2, j : j + 2] = ((cosine, sine), (-sine, cosine))
        return matrix

    def estimate(self, sensors: Sensors) -> tuple[float, float]:
        sampled, sequence = sensors.surface_sample_time_us, sensors.surface_sequence
        if (
            sensors.surface_fresh
            and sensors.surface_z_m is not None
            and math.isfinite(sensors.surface_z_m)
            and sampled is not None
            and sequence is not None
            and sampled >= 0
            and sampled + self.delay_us <= sensors.time_us
            and (self._sample_time_us is None or sampled > self._sample_time_us)
            and (self._sequence is None or sequence > self._sequence)
        ):
            if self._sample_time_us is not None:
                # Filter state lives at capture time, not delivery time.
                elapsed = sampled - self._sample_time_us
                transition = self.transition(elapsed)
                self._state = transition @ self._state
                process_root = self.process_std_m_sqrt_s * math.sqrt(elapsed * 1e-6)
                self._covariance_root = self._lower_root(
                    np.hstack((transition @ self._covariance_root, self._identity * process_root))
                )
            h = self._position_row
            # Triangularize the joint innovation/state covariance root. Its lower
            # right block is the posterior root and its first column gives K.
            size = self._state.size
            joint = np.zeros((size + 1, size + 1))
            joint[0, 0] = self.measurement_std_m
            joint[0, 1:] = h @ self._covariance_root
            joint[1:, 1:] = self._covariance_root
            posterior = self._lower_root(joint)
            gain = posterior[1:, 0] / posterior[0, 0]
            self._state += gain * (sensors.surface_z_m - h @ self._state)
            self._covariance_root = posterior[1:, 1:]
            self._sample_time_us, self._sequence = sampled, sequence

        if self._sample_time_us is None:
            return 0.0, 0.0
        # Nominal age is exactly 15 ms. Between sparse/lost frames it also includes
        # the elapsed hold interval. This output prediction never alters the filter.
        current = self.transition(sensors.time_us - self._sample_time_us) @ self._state
        return float(self._position_row @ current), float(self._velocity_row @ current)


@dataclass(slots=True)
class PreviewFeedback(DelayedFeedback):
    estimator: HarmonicSurfaceEstimator

    def command(self, sensors: Sensors) -> Command:
        surface_z, surface_v = self.estimator.estimate(sensors)
        gap_ref, gap_v_ref = reference(
            sensors.time_us, self.initial_height, self.hover_height, self.insertion_depth
        )
        # Same PD arithmetic/gains; only the surface position and velocity change.
        return Command(
            self.kp * (gap_ref + surface_z - sensors.needle_z_m)
            + self.kd * (gap_v_ref + surface_v - sensors.needle_v_m_s)
        )
