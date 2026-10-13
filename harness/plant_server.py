"""Bounded binary pipe server around the unchanged Phase A MuJoCo plant.

Only Sensors crosses the controller boundary. Canonical trace/truth bytes return
separately to the host logger; the Rust controller never receives Truth.
"""

import argparse
import math
import struct
import sys
from dataclasses import asdict

from sim.config import Config
from sim.contracts import Command
from sim.plant import MujocoPlant
from sim.run import canonical

from .c32 import input_value
from .run import evaluation_row

LIMIT = 1024 * 1024
SENSOR = struct.Struct("<IIIIdddB")


def sensor_bytes(sensors):
    c = input_value(sensors)
    return SENSOR.pack(
        c.tick,
        c.time_us,
        c.sample_time_us,
        c.sequence,
        sensors.needle_z_m,
        sensors.needle_v_m_s,
        sensors.surface_z_m if c.flags else 0.0,
        c.flags,
    )


def read_exact(stream, count):
    result = bytearray()
    while len(result) < count:
        part = stream.read(count - len(result))
        if not part:
            raise EOFError("truncated IPC request")
        result.extend(part)
    return bytes(result)


def read_packet(stream):
    (size,) = struct.unpack("<I", read_exact(stream, 4))
    if not 1 <= size <= LIMIT:
        raise ValueError("invalid IPC request size")
    return read_exact(stream, size)


def write_packet(stream, payload):
    if not 1 <= len(payload) <= LIMIT:
        raise ValueError("invalid IPC response size")
    stream.write(struct.pack("<I", len(payload)) + payload)
    stream.flush()


def serve(source, destination, profile):
    cfg = Config(controller="preview", contact_profile=profile)
    plant = None
    while True:
        request = read_packet(source)
        if request[0] == 1:
            if plant is not None or len(request) != 9 or struct.unpack("<Q", request[1:])[0] != 42:
                raise ValueError("invalid nominal reset")
            plant = MujocoPlant(cfg)
            response = b"\x81" + sensor_bytes(plant.sensors)
        elif request[0] == 2:
            if plant is None or len(request) != 9:
                raise ValueError("step before reset or wrong length")
            tick, force = struct.unpack("<If", request[1:])
            if tick != plant.tick or tick >= 8000 or not math.isfinite(force):
                raise ValueError("invalid tick/force")
            sensors = plant.sensors
            command = Command(force_n=force)
            truth = canonical(evaluation_row(cfg, sensors, plant.truth()))
            trace = canonical({"sensors": asdict(sensors), "command": asdict(command)})
            plant.step(command, cfg.control_dt_us)
            if not plant.healthy():
                raise RuntimeError("MuJoCo warning or nonfinite state")
            response = (
                b"\x82"
                + sensor_bytes(plant.sensors)
                + struct.pack("<I", len(trace))
                + trace
                + struct.pack("<I", len(truth))
                + truth
            )
        elif request[0] == 3:
            if plant is None or len(request) != 5:
                raise ValueError("invalid finish")
            (ticks,) = struct.unpack("<I", request[1:])
            if ticks != 8000 or plant.tick != ticks:
                raise ValueError("incomplete run")
            write_packet(destination, b"\x83" + request[1:])
            return
        else:
            raise ValueError("unknown IPC operation")
        write_packet(destination, response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contact-profile", choices=("primary", "paper_effective"), required=True)
    args = parser.parse_args()
    try:
        serve(sys.stdin.buffer, sys.stdout.buffer, args.contact_profile)
    except (ValueError, RuntimeError, OSError, EOFError) as exc:
        write_packet(sys.stdout.buffer, b"\xff" + str(exc).encode()[:1024])
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
