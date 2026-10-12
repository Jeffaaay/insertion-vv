"""Typed C ABI boundary. Only Sensors cross into the portable controller."""

import ctypes as ct
import json
from pathlib import Path

from sim.contracts import Command, Sensors
from tools.build_controller import CTRL, digest


class Params(ct.Structure):
    _fields_ = (
        [
            (name, ct.c_float)
            for name in (
                "kp",
                "kd",
                "initial_height",
                "hover_height",
                "depth",
                "mass",
                "observer_position",
                "observer_velocity",
                "observer_acceleration",
            )
        ]
        + [("frequencies", ct.c_float * 3)]
        + [(name, ct.c_float) for name in ("initial_std", "measurement_std", "process_std")]
        + [("dt_us", ct.c_uint32), ("delay_us", ct.c_uint32)]
    )


class Input(ct.Structure):
    _fields_ = (
        [(name, ct.c_uint32) for name in ("tick", "time_us", "sample_time_us", "sequence")]
        + [
            (name, ct.c_float)
            for name in ("needle_position", "needle_velocity", "surface_position")
        ]
        + [("flags", ct.c_uint32)]
    )


class Output(ct.Structure):
    _fields_ = [("force", ct.c_float)]


def input_value(sensors: Sensors) -> Input:
    valid = all(
        v is not None
        for v in (sensors.surface_z_m, sensors.surface_sample_time_us, sensors.surface_sequence)
    )
    integers = (
        sensors.tick,
        sensors.time_us,
        sensors.surface_sample_time_us if valid else 0,
        sensors.surface_sequence if valid else 0,
    )
    if any(type(v) is not int or not 0 <= v <= 0xFFFFFFFF for v in integers):
        raise ValueError("controller input does not fit the u32 ABI")
    return Input(
        *integers,
        sensors.needle_z_m,
        sensors.needle_v_m_s,
        sensors.surface_z_m if valid else 0.0,
        int(valid) | (2 if sensors.surface_fresh else 0),
    )


class ControllerC32:
    def __init__(self, build_directory: Path):
        directory = Path(build_directory).resolve()
        self.build = json.loads((directory / "build.json").read_text(encoding="utf-8"))
        for name, expected in self.build["sources"].items():
            if digest(CTRL / name) != expected:
                raise ValueError("stale C build; rebuild before running")
        library = directory / self.build["host"]["library"]
        if digest(library) != self.build["host"]["sha256"]:
            raise ValueError("C library SHA does not match build provenance")
        self.lib = ct.CDLL(str(library))
        for name in ("state", "params", "sensors"):
            fn = getattr(self.lib, f"ctrl_{name}_size")
            fn.argtypes, fn.restype = [], ct.c_size_t
        if self.lib.ctrl_params_size() != ct.sizeof(Params) or (
            self.lib.ctrl_sensors_size() != ct.sizeof(Input)
        ):
            raise ValueError("C/Python ABI mismatch")
        self.lib.ctrl_default_params.argtypes = [ct.POINTER(Params)]
        self.lib.ctrl_default_params.restype = None
        self.lib.ctrl_init.argtypes = [ct.c_void_p, ct.POINTER(Params)]
        self.lib.ctrl_init.restype = ct.c_int
        self.lib.ctrl_step.argtypes = [ct.c_void_p, ct.POINTER(Input), ct.POINTER(Output)]
        self.lib.ctrl_step.restype = ct.c_int
        # uint64 storage is at least as aligned as every float/u32 field in CtrlState.
        self.state = (ct.c_uint64 * ((self.lib.ctrl_state_size() + 7) // 8))()
        self.params = Params()
        self.lib.ctrl_default_params(ct.byref(self.params))
        self.reset()

    def reset(self):
        if self.lib.ctrl_init(self.state, ct.byref(self.params)):
            raise ValueError("C controller initialization rejected")

    def command(self, sensors: Sensors) -> Command:
        inputs, output = input_value(sensors), Output()
        if self.lib.ctrl_step(self.state, ct.byref(inputs), ct.byref(output)):
            raise ValueError(f"C controller rejected tick {sensors.tick}")
        return Command(float(output.force))

    def parameter_values(self):
        return {
            name: list(getattr(self.params, name))
            if name == "frequencies"
            else getattr(self.params, name)
            for name, _ in Params._fields_
        }
