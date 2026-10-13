"""Synthetic parser/gate tests only; none of these fixtures are hardware evidence."""

import binascii
import json
import struct
import zlib

import pytest

from harness.replay_report import analyze, extract_lockstep, frame
from tools import board


def packet(kind, session, payload=b""):
    raw = struct.pack("<BBHI", 1, kind, len(payload), session) + payload
    return b"\xa5\x5a" + raw + struct.pack("<H", binascii.crc_hqx(raw, 0xFFFF))


def synthetic_replay(compute=5200, jitter=0, headroom=8000, late=False):
    arm, period = 0xFFF00000, 520000
    inputs = b"".join(
        struct.pack("<IIIIfffB", k, k * 1000, 0, 0, 0.001, 0, 0, 0) for k in range(8000)
    )
    rows, timings, forces = bytearray(), bytearray(), bytearray()
    for k in range(8000):
        entry = (arm + (k + 1) * period + (jitter if k % 2 else 0)) % 2**32
        body = compute + 300
        status = 0x80 if late and k == 100 else 0
        if status:
            body = period + 1
        rows.extend(struct.pack("<IfIIB", k, -0.001, entry, compute, status))
        timings.extend(struct.pack("<II", 100, body))
        forces.extend(struct.pack("<f", -0.001))
    last = (entry + compute + 200) % 2**32
    words = [
        2,
        8000,
        8000,
        int(late),
        zlib.crc32(inputs),
        zlib.crc32(rows),
        8000,
        arm,
        (arm + 20) % 2**32,
        last,
        headroom,
        16000,
        0,
        520000000,
        260000000,
        5,
        1234,
        31104,
        int(late),
        period,
        zlib.crc32(timings),
    ]
    return [bytes(rows), bytes(timings), bytes(forces), inputs, words]


def test_replay_wrap_and_registered_gate_boundaries():
    result = analyze(*synthetic_replay())
    assert result["status"] == "PASS"
    assert result["compute_us"]["p99"] == 10
    assert result["absolute_period_jitter_us"]["max"] == 0
    assert result["clock_accuracy"].startswith("UNVERIFIED")
    assert analyze(*synthetic_replay(headroom=4096))["status"] == "PASS"
    for changes in ({"headroom": 4095}, {"compute": 52000}, {"jitter": 2600}, {"late": True}):
        assert analyze(*synthetic_replay(**changes))["status"] == "FAIL"


def test_max_compute_tick_remains_visible_when_p99_passes():
    data = synthetic_replay()
    raw, timing = bytearray(data[0]), bytearray(data[1])
    struct.pack_into("<I", raw, 17 * 17 + 12, 78000)
    struct.pack_into("<I", timing, 17 * 8 + 4, 78300)
    data[0], data[1] = bytes(raw), bytes(timing)
    data[4][5], data[4][20] = zlib.crc32(raw), zlib.crc32(timing)
    report = analyze(*data)
    assert report["status"] == "PASS" and report["compute_us"]["p99"] == 10
    assert report["max_compute"] == {
        "tick": 17,
        "cycles": 78000,
        "us": 150,
        "ties": "first tick reported",
    }
    assert report["first_tick_compute_us"] == 10 and report["warmup_ticks_excluded"] == 0


@pytest.mark.parametrize(
    "case",
    [
        "crc",
        "truncated",
        "force",
        "missing_miss",
        "summary",
        "end",
        "clock",
        "float_word",
        "tick",
        "body",
    ],
)
def test_corrupt_or_inconsistent_replay_is_invalid(case):
    data = synthetic_replay(late=case == "missing_miss")
    if case == "crc":
        data[0] = bytes([data[0][0] ^ 1]) + data[0][1:]
    elif case == "truncated":
        data[1] = data[1][:-1]
    elif case == "force":
        data[2] = bytes([data[2][0] ^ 1]) + data[2][1:]
    elif case in ("missing_miss", "tick"):
        raw = bytearray(data[0])
        raw[100 * 17 + (16 if case == "missing_miss" else 0)] = 0
        data[0] = bytes(raw)
        data[4][5] = zlib.crc32(raw)
        if case == "missing_miss":
            data[4][3] = data[4][18] = 0
    elif case == "summary":
        data[4][2] -= 1
    elif case == "end":
        data[4][9] += 10000
    elif case == "clock":
        data[4][13] = 480000000
    elif case == "float_word":
        data[4][12] = 0.0
    elif case == "body":
        raw = bytearray(data[1])
        struct.pack_into("<I", raw, 4, 1)
        data[1] = bytes(raw)
        data[4][20] = zlib.crc32(raw)
    with pytest.raises(ValueError):
        analyze(*data)


def transcript(root):
    info = dict(
        device_kind=1,
        abi=1,
        capabilities=3,
        core_clock_hz=520000000,
        timer_clock_hz=260000000,
        max_ticks=8000,
        git_commit="a" * 40,
        controller_source_sha256="b" * 64,
        unique_id_hex="01" * 12,
        mcu_idcode=0x483,
        arm_cpuid=0x410FC271,
    )
    hello = struct.pack(
        "<BBHIII40s64s12sII",
        1,
        1,
        3,
        520000000,
        260000000,
        8000,
        b"a" * 40,
        b"b" * 64,
        b"\x01" * 12,
        0x483,
        0x410FC271,
    )
    exchanges = [
        (packet(1, 0), packet(0x81, 0, hello)),
        (packet(2, 123, struct.pack("<BI", 0, 8000)), packet(0x82, 123, b"\x02\0")),
    ]
    trace = []
    for k in range(8000):
        row = {
            "sensors": {
                "tick": k,
                "time_us": k * 1000,
                "needle_z_m": 0.001,
                "needle_v_m_s": 0,
                "surface_z_m": None,
                "surface_sequence": None,
                "surface_sample_time_us": None,
                "surface_fresh": False,
            },
            "command": {"force_n": -0.001},
        }
        trace.append(json.dumps(row))
        exchanges.append(
            (
                packet(3, 123, struct.pack("<IIIIfffB", k, k * 1000, 0, 0, 0.001, 0, 0, 0)),
                packet(0x83, 123, struct.pack("<IfIIB", k, -0.001, 10, 20, 0)),
            )
        )
    exchanges.append((packet(4, 123, struct.pack("<I", 8000)), packet(0x82, 123, b"\x04\0")))
    events = []
    for tx, rx in exchanges:
        for direction, raw in (("tx", tx), ("rx", rx)):
            events.append(
                {"direction": direction, "elapsed_ns": len(events) * 100000, "hex": raw.hex()}
            )
    trace = ("\n".join(trace) + "\n").encode()
    (root / "trace.jsonl").write_bytes(trace)
    (root / "truth.jsonl").write_bytes(b"synthetic test sentinel\n")
    board.save(
        root / "completion.json",
        {
            "status": "COMPLETE",
            "completed_ticks": 8000,
            "controller": {"backend": "serial", "info": info, "session": 123},
            "trace_sha256": board.sha(trace),
            "truth_sha256": board.sha(b"synthetic test sentinel\n"),
        },
    )
    return info, events


@pytest.mark.parametrize("fault", [None, "hello", "finish", "crc", "command", "timestamp"])
def test_recorded_transcript_requires_identity_crc_commands_and_finish(tmp_path, fault):
    info, events = transcript(tmp_path)
    if fault == "hello":
        raw = bytearray(bytes.fromhex(events[1]["hex"])[10:-2])
        raw[120] ^= 1
        events[1]["hex"] = packet(0x81, 0, raw).hex()
    elif fault == "finish":
        events.pop()
    elif fault == "crc":
        events[100]["hex"] = events[100]["hex"][:-2] + "00"
    elif fault == "command":
        kind, session, raw = frame(bytes.fromhex(events[101]["hex"]))
        raw = raw[:4] + struct.pack("<f", 0.01) + raw[8:]
        events[101]["hex"] = packet(kind, session, raw).hex()
    elif fault == "timestamp":
        events[100]["elapsed_ns"] = 0
    (tmp_path / "transport.jsonl").write_text("\n".join(json.dumps(v) for v in events))
    if fault:
        with pytest.raises(ValueError):
            extract_lockstep(tmp_path, info)
    else:
        inputs, force, rtt = extract_lockstep(tmp_path, info)
        assert (len(inputs), len(force), len(rtt)) == (232000, 32000, 8000)
        assert rtt == [100] * 8000


@pytest.mark.parametrize(
    "change",
    [
        {"mcu_idcode": 0x450},
        {"arm_cpuid": 0xC240},
        {"flash_bytes": 2097152},
        {"unique_id_hex": "00" * 12},
        {"option_status_current": 0xBB00},
    ],
)
def test_wrong_or_protected_device_stops_before_programming(tmp_path, monkeypatch, change):
    identity = {
        "mcu_idcode": 0x483,
        "arm_cpuid": 0x410FC271,
        "flash_bytes": 1048576,
        "unique_id_hex": "01" * 12,
        "option_status_current": 0xAA00,
    }
    board.check_identity(identity)
    identity.update(change)
    firmware = tmp_path / "firmware"
    firmware.mkdir()
    meta = {"git_commit": "a" * 40, "binary_sha256": "b" * 64}
    board.save(
        tmp_path / "ci_origin.json",
        {"commit": meta["git_commit"], "binary_sha256": meta["binary_sha256"]},
    )
    monkeypatch.setattr(board, "validate_firmware", lambda _: meta)
    monkeypatch.setattr(board, "identify", lambda *args: identity)
    calls = []
    monkeypatch.setattr(board, "openocd", lambda *args: calls.append(args))
    with pytest.raises(ValueError):
        board.flash("unused", "unused", "1234", firmware, tmp_path / "attempt")
    assert calls == []


def test_tcl_and_output_boundaries_preserve_evidence(tmp_path, monkeypatch, capsys):
    for value in ("1234;shutdown", "[exit]", "abc\nexit"):
        with pytest.raises(ValueError):
            board.probe_serial(value)
    for value in ("a}b", "a{b", "a\nb"):
        with pytest.raises(ValueError):
            board.tcl_path(tmp_path / value)
    (tmp_path / "prior.txt").write_text("keep")
    monkeypatch.setattr("sys.argv", ["board", "prepare", "--run", "1", "--output", str(tmp_path)])
    assert board.main() == 2
    assert json.loads(capsys.readouterr().out)["status"] == "INVALID"
    assert [p.name for p in tmp_path.iterdir()] == ["prior.txt"]


def test_corrupted_firmware_rejected_before_hardware(tmp_path, monkeypatch):
    monkeypatch.setattr(board, "ROOT", tmp_path)
    source = tmp_path / "main.c"
    source.write_text("/* synthetic fixture */")
    binary = struct.pack("<II", 0x20020000, 0x08000009)
    (tmp_path / "insertion-h723.bin").write_bytes(binary)
    (tmp_path / "insertion-h723.elf").write_bytes(b"synthetic")
    meta = {
        "status": "PASS",
        "git_dirty": False,
        "git_commit": "a" * 40,
        "binary_sha256": board.sha(binary),
        "elf_sha256": board.sha(b"synthetic"),
        "binary_bytes": 8,
        "sources": {"main.c": board.sha(source.read_bytes())},
        "configured_hardware": {"replay_implemented": True},
    }
    board.save(tmp_path / "build.json", meta)
    assert board.validate_firmware(tmp_path) == meta
    source.write_text("changed")
    with pytest.raises(ValueError, match="sources differ"):
        board.validate_firmware(tmp_path)
    (tmp_path / "insertion-h723.bin").write_bytes(binary + b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        board.validate_firmware(tmp_path)
