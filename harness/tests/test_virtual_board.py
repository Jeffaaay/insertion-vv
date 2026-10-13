import binascii
import os
import socket
import struct
from pathlib import Path

import pytest

from harness.virtual_board import launch


def frame(kind, session, payload=b""):
    message = struct.pack("<BBHI", 1, kind, len(payload), session) + payload
    return b"\xa5\x5a" + message + struct.pack("<H", binascii.crc_hqx(message, 0xFFFF))


def read_exact(peer, count):
    result = bytearray()
    while len(result) < count:
        part = peer.recv(count - len(result))
        assert part, "unexpected EOF"
        result.extend(part)
    return bytes(result)


def response(peer):
    header = read_exact(peer, 10)
    assert header[:3] == b"\xa5\x5a\x01"
    length = struct.unpack_from("<H", header, 4)[0]
    assert length <= 256
    tail = read_exact(peer, length + 2)
    assert binascii.crc_hqx(header[2:] + tail[:-2], 0xFFFF) == struct.unpack("<H", tail[-2:])[0]
    return header[3], tail[:-2]


def test_c_virtual_board_aborts_corrupt_crc(tmp_path):
    with pytest.raises(ValueError, match="session failed"):
        with launch(Path(os.environ["C32_BUILD"]), tmp_path / "board") as (address, _):
            host, port = address.split(":")
            with socket.create_connection((host, int(port)), timeout=2) as peer:
                corrupt = bytearray(frame(1, 0))
                corrupt[-1] ^= 1
                peer.sendall(corrupt)
                assert peer.recv(1) == b""


def test_c_virtual_board_rejects_duplicate_tick(tmp_path):
    with pytest.raises(ValueError, match="session failed"):
        with launch(Path(os.environ["C32_BUILD"]), tmp_path / "board") as (address, metadata):
            host, port = address.split(":")
            with socket.create_connection((host, int(port)), timeout=2) as peer:
                peer.sendall(frame(1, 0))
                kind, info = response(peer)
                assert kind == 0x81 and len(info) == 140
                assert info[56:120].decode() == metadata["controller_source_sha256"]
                peer.sendall(frame(2, 123, struct.pack("<BI", 0, 8000)))
                assert response(peer) == (0x82, b"\x02\x00")
                sensors = struct.pack("<IIIIfffB", 0, 0, 0, 0, 0.001, 0, 0, 0)
                peer.sendall(frame(3, 123, sensors))
                kind, command = response(peer)
                assert kind == 0x83 and len(command) == 17 and command[16] == 0
                peer.sendall(frame(3, 123, sensors))
                kind, command = response(peer)
                assert kind == 0x83 and command[16] == 2
