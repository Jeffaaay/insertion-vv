"""Independently verify recorded UART inputs, replay CRCs and timing gates."""

import binascii
import json
import math
import struct
import zlib
from pathlib import Path

from tools.board import sha


def frame(data):
    if len(data) < 12 or data[:3] != b"\xa5\x5a\x01":
        raise ValueError("invalid recorded wire frame")
    count = int.from_bytes(data[4:6], "little")
    if count > 256 or len(data) != count + 12:
        raise ValueError("recorded frame length mismatch")
    if binascii.crc_hqx(data[2:-2], 0xFFFF) != int.from_bytes(data[-2:], "little"):
        raise ValueError("recorded frame CRC16 mismatch")
    return data[3], int.from_bytes(data[6:10], "little"), data[10:-2]


def extract_lockstep(directory, expected_info):
    directory = Path(directory)
    completion = json.loads((directory / "completion.json").read_text())
    if (
        completion["status"] != "COMPLETE"
        or completion["completed_ticks"] != 8000
        or completion["controller"]["backend"] != "serial"
        or completion["controller"]["info"] != expected_info
    ):
        raise ValueError("input source is not a complete run from this board binary")
    trace_bytes = (directory / "trace.jsonl").read_bytes()
    truth_bytes = (directory / "truth.jsonl").read_bytes()
    if (
        sha(trace_bytes) != completion["trace_sha256"]
        or sha(truth_bytes) != completion["truth_sha256"]
    ):
        raise ValueError("source lockstep checksum mismatch")
    trace = [json.loads(line) for line in trace_bytes.splitlines()]
    events = [json.loads(line) for line in (directory / "transport.jsonl").read_text().splitlines()]
    if len(events) != 2 * (8000 + 3) or len(trace) != 8000:
        raise ValueError("incomplete wire/trace evidence")
    session = completion["controller"]["session"]
    timestamps = [event["elapsed_ns"] for event in events]
    if any(type(v) is not int or v < 0 for v in timestamps) or any(
        a >= b for a, b in zip(timestamps, timestamps[1:])
    ):
        raise ValueError("invalid transport timestamps")
    inputs, forces, rtt_us = bytearray(), bytearray(), []
    # The complete transcript must be HELLO, RESET, each tick, FINISH in order.
    for i, (tx, rx) in enumerate(zip(events[::2], events[1::2], strict=True)):
        if tx["direction"] != "tx" or rx["direction"] != "rx" or rx.get("error"):
            raise ValueError("invalid transport event ordering/error")
        kind, tx_session, payload = frame(bytes.fromhex(tx["hex"]))
        reply, rx_session, result = frame(bytes.fromhex(rx["hex"]))
        expected_type = 1 if i == 0 else 2 if i == 1 else 4 if i == 8002 else 3
        if (
            kind != expected_type
            or tx_session != (0 if i == 0 else session)
            or rx_session != tx_session
        ):
            raise ValueError("wire session/type differs from complete lockstep")
        if i == 0:
            if payload or reply != 0x81 or len(result) != 140:
                raise ValueError("invalid HELLO transcript")
            values = struct.unpack("<BBHIII40s64s12sII", result)
            decoded = dict(
                zip(
                    (
                        "device_kind",
                        "abi",
                        "capabilities",
                        "core_clock_hz",
                        "timer_clock_hz",
                        "max_ticks",
                        "git_commit",
                        "controller_source_sha256",
                        "unique_id_hex",
                        "mcu_idcode",
                        "arm_cpuid",
                    ),
                    values,
                    strict=True,
                )
            )
            decoded["git_commit"] = decoded["git_commit"].decode("ascii")
            decoded["controller_source_sha256"] = decoded["controller_source_sha256"].decode(
                "ascii"
            )
            decoded["unique_id_hex"] = decoded["unique_id_hex"].hex()
            if decoded != expected_info:
                raise ValueError("recorded HELLO differs from verified identity")
        elif i == 1:
            if payload != struct.pack("<BI", 0, 8000) or reply != 0x82 or result != b"\x02\0":
                raise ValueError("invalid RESET transcript")
        elif i == 8002:
            if payload != struct.pack("<I", 8000) or reply != 0x82 or result != b"\x04\0":
                raise ValueError("missing FINISH acknowledgement")
        else:
            k = i - 2
            if len(payload) != 29 or reply != 0x83 or len(result) != 17:
                raise ValueError("wrong input/command payload")
            row = trace[k]
            s = row["sensors"]
            valid = s["surface_z_m"] is not None
            wanted = struct.pack(
                "<IIIIfffB",
                k,
                k * 1000,
                s["surface_sample_time_us"] if valid else 0,
                s["surface_sequence"] if valid else 0,
                s["needle_z_m"],
                s["needle_v_m_s"],
                s["surface_z_m"] if valid else 0,
                (1 | (2 if s["surface_fresh"] else 0)) if valid else 0,
            )
            if payload != wanted or s["tick"] != k or s["time_us"] != k * 1000:
                raise ValueError("recorded wire input differs from quantized source trace")
            if (
                int.from_bytes(result[:4], "little") != k
                or result[16]
                or result[4:8] != struct.pack("<f", row["command"]["force_n"])
            ):
                raise ValueError("wire command differs from source trace")
            elapsed = rx["elapsed_ns"] - tx["elapsed_ns"]
            if elapsed <= 0:
                raise ValueError("invalid transport timestamps")
            inputs.extend(payload)
            forces.extend(result[4:8])
            rtt_us.append(elapsed / 1000)
    return bytes(inputs), bytes(forces), rtt_us


def percentiles(values):
    if not values or not all(math.isfinite(v) for v in values):
        raise ValueError("missing/nonfinite timing samples")
    values = sorted(values)

    def at(percent):
        index = (len(values) - 1) * percent / 100
        low, high = math.floor(index), math.ceil(index)
        return values[low] + (values[high] - values[low]) * (index - low)

    return {
        "samples": len(values),
        "min": values[0],
        "p50": at(50),
        "p95": at(95),
        "p99": at(99),
        "max": values[-1],
    }


def analyze(commands, timings, expected_forces, inputs, words):
    if any(type(v) is not int or not 0 <= v < 2**32 for v in words):
        raise ValueError("invalid summary words")
    if (
        len(words) != 21
        or words[0] != 2
        or words[1] != 8000
        or words[2] != 8000
        or words[6] != 8000
    ):
        raise ValueError("replay is incomplete")
    if (
        len(commands) != 136000
        or len(timings) != 64000
        or len(expected_forces) != 32000
        or len(inputs) != 232000
    ):
        raise ValueError("replay evidence length mismatch")
    if (zlib.crc32(commands), zlib.crc32(timings), zlib.crc32(inputs)) != (
        words[5],
        words[20],
        words[4],
    ):
        raise ValueError("whole-stream CRC32 mismatch")
    if words[13:16] != [520000000, 260000000, 5] or words[19] != 520000:
        raise ValueError("clock/cache/replay configuration changed")
    if words[12] & ((3 << 22) | (7 << 24)):
        raise ValueError("FPU rounding/flush/default-NaN configuration changed")
    if not 0 <= words[10] <= words[11] <= 16384 or (words[8] - words[7]) % 2**32 >= words[19]:
        raise ValueError("invalid stack/start-window metadata")
    rows = list(struct.iter_unpack("<IfIIB", commands))
    extra = list(struct.iter_unpack("<II", timings))
    if [r[0] for r in rows] != list(range(8000)) or any(
        r[4] & 0x7F or not math.isfinite(r[1]) for r in rows
    ):
        raise ValueError("invalid replay command/tick/status")
    force_bits = b"".join(commands[i + 4 : i + 8] for i in range(0, len(commands), 17))
    if force_bits != expected_forces:
        raise ValueError("same-board replay command bits differ from lockstep")
    misses = sum(bool(r[4] & 0x80) for r in rows)
    if misses != words[3] or words[18] > misses:
        raise ValueError("deadline flag/summary mismatch")
    deltas = [(rows[k][2] - rows[k - 1][2]) % 2**32 for k in range(1, 8000)]
    if any(v == 0 or v >= 2**31 for v in deltas):
        raise ValueError("ambiguous/invalid adjacent DWT interval")
    if any(
        start + row[3] > body or row[3] == 0 for row, (start, body) in zip(rows, extra, strict=True)
    ):
        raise ValueError("inconsistent timing boundaries")
    last_elapsed = (words[9] - rows[-1][2]) % 2**32
    if not extra[-1][0] + rows[-1][3] <= last_elapsed <= extra[-1][1]:
        raise ValueError("last ISR end differs from summary")
    # Recheck absolute schedule with the earlier arm bound and measured ISR body.
    elapsed = (rows[0][2] - words[7]) % 2**32
    for k, (row, (_, body)) in enumerate(zip(rows, extra, strict=True)):
        if k:
            elapsed += deltas[k - 1]
        if elapsed + body >= (k + 2) * words[19] and not row[4] & 0x80:
            raise ValueError("unreported scheduled deadline miss")
    divisor = words[13] / 1e6
    compute = percentiles([r[3] / divisor for r in rows])
    max_tick = max(range(8000), key=lambda k: rows[k][3])
    jitter_values = [(d - words[19]) / divisor for d in deltas]
    absolute_jitter = percentiles([abs(v) for v in jitter_values])
    checks = {
        "compute_p99_below_100_us": compute["p99"] < 100,
        "absolute_jitter_p99_below_5_us": absolute_jitter["p99"] < 5,
        "zero_deadline_misses": misses == 0,
        "zero_UIF_overruns": words[18] == 0,
        "stack_headroom_at_least_4096_bytes": words[10] >= 4096,
        "all_8000_command_bits_equal_lockstep": True,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "compute_us": compute,
        "max_compute": {
            "tick": max_tick,
            "cycles": rows[max_tick][3],
            "us": rows[max_tick][3] / divisor,
            "ties": "first tick reported",
        },
        "first_tick_compute_us": rows[0][3] / divisor,
        "warmup_ticks_excluded": 0,
        "signed_period_jitter_us": percentiles(jitter_values),
        "absolute_period_jitter_us": absolute_jitter,
        "entry_to_control_us": percentiles([v[0] / divisor for v in extra]),
        "measured_isr_body_us": percentiles([v[1] / divisor for v in extra]),
        "stack_untouched_prefix_bytes": words[10],
        "deadline_misses": misses,
        "UIF_overruns": words[18],
        "arm_window_cycles": (words[8] - words[7]) % 2**32,
        "input_sha256": sha(inputs),
        "force_bits_sha256": sha(force_bits),
        "clock_accuracy": "UNVERIFIED: TIM6 and DWT share a clock; external instrument required",
        "isr_body_scope": "excludes final timestamp/store, GPIO clear and exception epilogue",
    }
