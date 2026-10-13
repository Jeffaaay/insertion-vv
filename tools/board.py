"""Prepare CI firmware, identify/backup H723, and explicitly flash with readback."""

import argparse
import hashlib
import json
import re
import struct
import subprocess
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "Jeffaaay/insertion-vv"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def fresh(path):
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    if any(path.iterdir()):
        raise ValueError("output must be empty; preserve earlier hardware evidence")
    return path


def validate_firmware(directory):
    directory = Path(directory).resolve()
    meta = json.loads((directory / "build.json").read_text())
    if (
        meta["status"] != "PASS"
        or meta["git_dirty"]
        or not re.fullmatch(r"[0-9a-f]{40}", meta["git_commit"])
    ):
        raise ValueError("firmware must be a clean, successful recorded build")
    for filename, key in (
        ("insertion-h723.bin", "binary_sha256"),
        ("insertion-h723.elf", "elf_sha256"),
    ):
        if sha((directory / filename).read_bytes()) != meta[key]:
            raise ValueError("firmware artifact checksum mismatch")
    binary = (directory / "insertion-h723.bin").read_bytes()
    if len(binary) != meta["binary_bytes"] or not 8 <= len(binary) <= 1048576:
        raise ValueError("firmware image size mismatch")
    sp, reset = struct.unpack("<II", binary[:8])
    if sp != 0x20020000 or not (0x08000001 <= reset < 0x08100000 and reset & 1):
        raise ValueError("unexpected boot vectors")
    for name, expected in meta["sources"].items():
        source = (ROOT / name).resolve()
        source.relative_to(ROOT)
        if sha(source.read_bytes()) != expected:
            raise ValueError(f"firmware sources differ: {name}")
    if not meta["configured_hardware"]["replay_implemented"]:
        raise ValueError("B1 image cannot perform B2 replay")
    return meta


def prepare(run_id, output):
    output = fresh(output)
    run = json.loads(
        subprocess.check_output(
            ["gh", "api", f"repos/{REPOSITORY}/actions/runs/{int(run_id)}"], text=True
        )
    )
    if not (
        run["conclusion"] == "success"
        and run["status"] == "completed"
        and run["head_branch"] == "main"
        and run["head_repository"]["full_name"] == REPOSITORY
        and run["event"] in ("push", "workflow_dispatch")
        and run["path"] == ".github/workflows/phase-b.yml"
    ):
        raise ValueError("require successful Phase B CI on this repository's main")
    commit = run["head_sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("invalid CI commit")
    for name, dest in (
        (f"phase-b-h723-{commit}", "firmware"),
        (f"phase-b-c32-ubuntu-24.04-{commit}", "linux-reference"),
    ):
        subprocess.run(
            [
                "gh",
                "run",
                "download",
                str(run_id),
                "--repo",
                REPOSITORY,
                "-n",
                name,
                "-D",
                str(output / dest),
            ],
            check=True,
            timeout=120,
        )
    meta = validate_firmware(output / "firmware")
    if meta["git_commit"] != commit:
        raise ValueError("CI and firmware commit differ")
    save(
        output / "ci_origin.json",
        {
            "run_id": int(run_id),
            "url": run["html_url"],
            "commit": commit,
            "binary_sha256": meta["binary_sha256"],
        },
    )
    return {"status": "PREPARED", "firmware": str(output / "firmware"), "hardware_verified": False}


def tcl_path(path):
    text = Path(path).resolve().as_posix()
    if any(char in text for char in "{}\n\r"):
        raise ValueError("unsupported Tcl path characters")
    return "{" + text + "}"


def probe_serial(value):
    if not re.fullmatch(r"[A-Za-z0-9_-]{4,80}", value):
        raise ValueError("invalid explicit ST-LINK probe serial")
    return value


def openocd(executable, scripts, probe, output, commands):
    script = output / "openocd.cfg"
    probe = probe_serial(probe)
    script.write_text(
        "gdb_port disabled\ntcl_port disabled\ntelnet_port disabled\n"
        "source [find interface/stlink.cfg]\n"
        f"adapter serial {probe}\ntransport select dapdirect_swd\n"
        "adapter speed 4000\nsource [find target/stm32h7x.cfg]\n" + commands + "\nshutdown\n",
        encoding="utf-8",
    )
    try:
        run = subprocess.run(
            [
                str(Path(executable).resolve()),
                "-s",
                str(Path(scripts).resolve()),
                "-f",
                str(script),
            ],
            capture_output=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        (output / "openocd.log").write_bytes((exc.stdout or b"") + (exc.stderr or b""))
        raise ValueError("OpenOCD timed out; no successful hardware operation claimed") from exc
    log = run.stdout + run.stderr
    (output / "openocd.log").write_bytes(log)
    if run.returncode:
        raise ValueError("OpenOCD failed; inspect preserved log")
    return log.decode("utf-8", errors="replace")


RDP_GUARD = (
    "if {(([lindex [read_memory 0x5200201c 32 1] 0] >> 8) & 255) != 170} "
    '{error "RDP is not Level 0; no unlock or programming allowed"}\n'
)

IDENTITY = """init
reset halt
dump_image {options} 0x5200201c 4
{rdp_guard}flash probe 0
dump_image {idcode} 0x5c001000 4
dump_image {cpuid} 0xe000ed00 4
dump_image {uid} 0x1ff1e800 12
dump_image {size} 0x1ff1e880 2
stm32h7x option_read 0 0x1c
stm32h7x option_read 0 0x38
"""


def identify(executable, scripts, probe, output):
    output = fresh(output)
    commands = IDENTITY.format(
        rdp_guard=RDP_GUARD,
        **{
            name: tcl_path(output / (name + ".bin"))
            for name in ("idcode", "cpuid", "uid", "size", "options")
        },
    )
    log = openocd(executable, scripts, probe, output, commands + "resume")

    def word(name):
        data = (output / (name + ".bin")).read_bytes()
        if len(data) != (2 if name == "size" else 4):
            raise ValueError("incomplete identity readback")
        return int.from_bytes(data, "little")

    meta = {
        "probe_serial": probe_serial(probe),
        "mcu_idcode": word("idcode"),
        "arm_cpuid": word("cpuid"),
        "unique_id_hex": (output / "uid.bin").read_bytes().hex(),
        "flash_bytes": word("size") * 1024,
        "option_status_current": word("options"),
        "openocd_executable_sha256": sha(Path(executable).read_bytes()),
        "openocd_log_sha256": sha((output / "openocd.log").read_bytes()),
        "stlink_version_lines": [line for line in log.splitlines() if "STLINK" in line.upper()],
    }
    check_identity(meta)
    meta["status"] = "IDENTIFIED"
    save(output / "identity.json", meta)
    return meta


def check_identity(meta):
    if (meta["mcu_idcode"] & 0xFFF) != 0x483 or ((meta["arm_cpuid"] >> 4) & 0xFFF) != 0xC27:
        raise ValueError("device is not the expected H72x/H73x Cortex-M7 family")
    if meta["flash_bytes"] != 1048576 or not re.fullmatch(r"[0-9a-f]{24}", meta["unique_id_hex"]):
        raise ValueError("unexpected Flash size/UID")
    if int(meta["unique_id_hex"], 16) in (0, (1 << 96) - 1):
        raise ValueError("invalid MCU identity")
    if ((meta["option_status_current"] >> 8) & 255) != 0xAA:
        raise ValueError("readout protection is enabled; never change option bytes automatically")


def flash(executable, scripts, probe, firmware, output):
    output = fresh(output)
    firmware = Path(firmware).resolve()
    meta = validate_firmware(firmware)
    origin = json.loads((firmware.parent / "ci_origin.json").read_text())
    if origin["commit"] != meta["git_commit"] or origin["binary_sha256"] != meta["binary_sha256"]:
        raise ValueError("firmware does not match prepared green CI artifact")
    identity = identify(executable, scripts, probe, output / "identify")
    check_identity(identity)
    uid_words = struct.unpack("<III", bytes.fromhex(identity["unique_id_hex"]))
    # Revalidate the same UID in the programming connection, before any write.
    guard = "init\nreset halt\n" + RDP_GUARD + "flash probe 0\n"
    for i, word in enumerate(uid_words):
        guard += (
            f"if {{[lindex [read_memory {0x1FF1E800 + 4 * i:#x} 32 1] 0] != {word}}} "
            '{error "board UID changed"}\n'
        )
    backup_dir = fresh(output / "backup")
    backup = backup_dir / "original-flash.bin"
    openocd(
        executable,
        scripts,
        probe,
        backup_dir,
        guard + f"dump_image {tcl_path(backup)} 0x08000000 1048576\nresume",
    )
    original = backup.read_bytes()
    if len(original) != 1048576:
        raise ValueError("incomplete backup; programming aborted")
    save(
        backup_dir / "backup.json",
        {"sha256": sha(original), "bytes": len(original), "identity": identity, "keep_local": True},
    )
    programmed = fresh(output / "program")
    readback = programmed / "readback.bin"
    binary = firmware / "insertion-h723.bin"
    # No unlock, mass-erase, protection or option-write command is used.
    commands = (
        guard + f"flash write_image erase {tcl_path(binary)} 0x08000000 bin\n"
        f"verify_image {tcl_path(binary)} 0x08000000 bin\n"
        f"dump_image {tcl_path(readback)} 0x08000000 {meta['binary_bytes']}\nreset run"
    )
    openocd(executable, scripts, probe, programmed, commands)
    if sha(readback.read_bytes()) != meta["binary_sha256"]:
        raise ValueError("readback SHA mismatch; hardware experiment forbidden")
    receipt = {
        "status": "FLASH_VERIFIED",
        "identity": identity,
        "firmware_git": meta["git_commit"],
        "binary_sha256": meta["binary_sha256"],
        "elf_sha256": meta["elf_sha256"],
        "readback_sha256": sha(readback.read_bytes()),
        "binary_crc32": zlib.crc32(binary.read_bytes()),
        "readback_file": str(readback),
        "backup_file": str(backup),
        "backup_sha256": sha(original),
        "controller_source_sha256": meta["controller_source_sha256"],
        "ci_origin": origin,
        "hardware_numerics_verified": False,
        "hardware_timing_verified": False,
    }
    save(output / "flash_receipt.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "identify", "flash"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", type=int)
    parser.add_argument("--openocd", type=Path)
    parser.add_argument("--scripts", type=Path)
    parser.add_argument("--probe")
    parser.add_argument("--firmware", type=Path)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        print(
            json.dumps(
                {"status": "INVALID", "error": "output must be empty; prior evidence preserved"}
            )
        )
        return 2
    try:
        if args.action == "prepare":
            if args.run is None:
                raise ValueError("prepare requires --run")
            result = prepare(args.run, args.output)
        else:
            if any(value is None for value in (args.openocd, args.scripts, args.probe)):
                raise ValueError("identify/flash require --openocd, --scripts and explicit --probe")
            if args.action == "identify":
                result = identify(args.openocd, args.scripts, args.probe, args.output)
            else:
                if args.firmware is None:
                    raise ValueError("flash requires --firmware")
                result = flash(args.openocd, args.scripts, args.probe, args.firmware, args.output)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        result = {"status": "INVALID", "error": str(exc)}
        # Preserve the failure alongside partial evidence, without replacing an earlier result.
        args.output.mkdir(parents=True, exist_ok=True)
        with (args.output / "failure.json").open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
    print(json.dumps(result, indent=2))
    return 2 if result["status"] == "INVALID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
