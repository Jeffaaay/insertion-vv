"""The only implemented task controller. It receives Sensors, never Truth."""

from dataclasses import dataclass

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
