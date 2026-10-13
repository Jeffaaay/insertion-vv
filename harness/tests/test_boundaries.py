import io
import struct

import pytest

from harness.compare import validate_metrics
from harness.plant_server import SENSOR, read_packet, sensor_bytes, serve
from sim.contracts import Sensors


def test_pipe_preserves_binary64_until_controller_boundary():
    sensors = Sensors(16, 16000, 0.00123456789012345, -0.000123456789, 0.00003456789, 1000, 1, True)
    values = SENSOR.unpack(sensor_bytes(sensors))
    assert values[:4] == (16, 16000, 1000, 1)
    assert values[4:] == (sensors.needle_z_m, sensors.needle_v_m_s, sensors.surface_z_m, 3)
    absent = SENSOR.unpack(sensor_bytes(Sensors(0, 0, 0.001, 0, None, None, None, False)))
    assert absent[2:4] == (0, 0) and absent[6:] == (0.0, 0)


@pytest.mark.parametrize("data", [b"", b"\x01", struct.pack("<I", 5) + b"\x01\x02"])
def test_truncated_pipe_is_not_a_valid_step(data):
    with pytest.raises(EOFError):
        read_packet(io.BytesIO(data))


@pytest.mark.parametrize("size", [0, 1048577, 0xFFFFFFFF])
def test_pipe_allocation_is_bounded(size):
    with pytest.raises(ValueError, match="size"):
        read_packet(io.BytesIO(struct.pack("<I", size)))


def packet(payload):
    return struct.pack("<I", len(payload)) + payload


def test_wrong_tick_and_early_finish_rejected():
    reset = packet(b"\x01" + struct.pack("<Q", 42))
    for request in (b"\x02" + struct.pack("<If", 1, 0), b"\x03" + struct.pack("<I", 8000)):
        with pytest.raises(ValueError):
            serve(io.BytesIO(reset + packet(request)), io.BytesIO(), "primary")


@pytest.mark.parametrize(
    "field,value",
    [
        ("samples", True),
        ("samples", 2),
        ("samples", 0),
        ("rms_e_um", -1),
        ("rms_e_um", True),
        ("peak_contact_force_mn", float("nan")),
    ],
)
def test_comparison_rejects_invalid_metrics(field, value):
    metrics = {"verdict_contract": {"free_window_us": [0, 1], "contact_window_us": [0, 1]}}
    for window in ("free", "contact"):
        metrics[window] = {
            "samples": 1,
            "rms_e_um": 1,
            "peak_abs_edot_mm_s": 1,
            "peak_contact_force_mn": 1,
        }
    rows = {"truth": [{"time_us": 0}]}
    validate_metrics(metrics, rows)
    metrics["free"][field] = value
    with pytest.raises(ValueError):
        validate_metrics(metrics, rows)
