"""Build the portable C32 controller; no simulation or visualization dependency."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "firmware/ctrl"
FLAGS = [
    "-std=c11",
    "-O2",
    "-ffp-contract=off",
    "-fno-fast-math",
    "-Wall",
    "-Wextra",
    "-Werror",
    "-Wdouble-promotion",
]
ARM_FLAGS = ["-mcpu=cortex-m7", "-mthumb", "-mfpu=fpv5-d16", "-mfloat-abi=hard"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output, cc=None, arm_cc=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    cc = (
        cc
        or os.environ.get("CC")
        or next((shutil.which(c) for c in ("cc", "gcc", "clang") if shutil.which(c)), None)
    )
    if not cc:
        raise RuntimeError("C11 host compiler required; pass --cc or CC")
    library = output / ("controller.dll" if os.name == "nt" else "libcontroller.so")
    sources = {p.name: digest(p) for p in (CTRL / "controller.c", CTRL / "controller.h")}
    compiler = subprocess.check_output([cc, "--version"], text=True).strip()
    shared_flags = ["-DCTRL_SHARED", "-shared"] + ([] if os.name == "nt" else ["-fPIC"])
    subprocess.run(
        [cc, *FLAGS, *shared_flags, str(CTRL / "controller.c"), "-o", str(library), "-lm"],
        check=True,
    )
    test = output / ("controller_test.exe" if os.name == "nt" else "controller_test")
    subprocess.run(
        [cc, *FLAGS, str(CTRL / "test_controller.c"), "-o", str(test), "-lm"], check=True
    )
    subprocess.run([str(test)], check=True)
    report = {
        "sources": sources,
        "host": {
            "compiler": compiler,
            "flags": FLAGS + shared_flags,
            "library": library.name,
            "sha256": digest(library),
        },
        "core_tests": "PASS",
    }
    numerical_build = {
        "compiler": compiler.splitlines()[0],
        "flags": FLAGS,
        "sources": sources,
        "math_link": "-lm; compiler target runtime (no fast-math, no contraction)",
    }
    report["numerical_build"] = numerical_build
    report["numerical_build_sha256"] = hashlib.sha256(
        (json.dumps(numerical_build, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()
    report["controller_source_sha256"] = hashlib.sha256(
        (CTRL / "controller.c").read_bytes() + b"\0" + (CTRL / "controller.h").read_bytes()
    ).hexdigest()
    identity = {
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "controller_source_sha256": report["controller_source_sha256"],
    }
    (output / "build_identity.h").write_text(
        '#define VV_BUILD_GIT "' + identity["git_commit"] + '"\n'
        '#define VV_CONTROLLER_SOURCE_SHA256 "' + identity["controller_source_sha256"] + '"\n',
        encoding="ascii",
    )
    protocol = ROOT / "firmware/protocol/protocol.c"
    protocol_test = output / ("protocol_test.exe" if os.name == "nt" else "protocol_test")
    subprocess.run(
        [
            cc,
            *FLAGS,
            str(CTRL / "controller.c"),
            str(protocol),
            str(protocol.with_name("test_protocol.c")),
            "-o",
            str(protocol_test),
            "-lm",
        ],
        check=True,
    )
    golden = json.loads((ROOT / "harness/tests/data/protocol_v1.json").read_text())
    subprocess.run(
        [str(protocol_test), *(row["frame_hex"] for row in golden["frames"])], check=True
    )
    replay_test = output / ("replay_test.exe" if os.name == "nt" else "replay_test")
    subprocess.run(
        [
            cc,
            *FLAGS,
            str(CTRL / "controller.c"),
            str(protocol),
            str(protocol.with_name("replay.c")),
            str(protocol.with_name("test_replay.c")),
            "-o",
            str(replay_test),
            "-lm",
        ],
        check=True,
    )
    subprocess.run([str(replay_test)], check=True)
    report["replay_tests"] = "PASS (synthetic clocks; not hardware timing)"
    virtual = output / ("virtual_board.exe" if os.name == "nt" else "virtual_board")
    virtual_flags = FLAGS + ([] if os.name == "nt" else ["-fPIC"])
    subprocess.run(
        [
            cc,
            *virtual_flags,
            "-I",
            str(output),
            str(CTRL / "controller.c"),
            str(protocol),
            str(ROOT / "firmware/virtual_board/main.c"),
            "-o",
            str(virtual),
            "-lm",
            *(["-lws2_32"] if os.name == "nt" else []),
        ],
        check=True,
    )
    report["virtual"] = {
        **identity,
        "executable": virtual.name,
        "sha256": digest(virtual),
        "compiler": compiler,
        "flags": virtual_flags,
        "numerical_build_sha256": report["numerical_build_sha256"],
        "sources": {
            p.relative_to(ROOT).as_posix(): digest(p)
            for p in (
                protocol,
                protocol.with_name("protocol.h"),
                ROOT / "firmware/virtual_board/main.c",
            )
        },
        "protocol_tests": "PASS",
    }
    if arm_cc:
        obj = output / "controller-cortex-m7.o"
        subprocess.run(
            [arm_cc, *FLAGS, *ARM_FLAGS, "-c", str(CTRL / "controller.c"), "-o", str(obj)],
            check=True,
        )
        report["arm"] = {
            "compiler": subprocess.check_output([arm_cc, "--version"], text=True).strip(),
            "flags": FLAGS + ARM_FLAGS,
            "object_sha256": digest(obj),
        }
        protocol_obj = output / "protocol-cortex-m7.o"
        subprocess.run(
            [arm_cc, *FLAGS, *ARM_FLAGS, "-c", str(protocol), "-o", str(protocol_obj)],
            check=True,
        )
        report["arm"]["protocol_object_sha256"] = digest(protocol_obj)
    (output / "build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cc")
    parser.add_argument("--arm-cc")
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.cc, args.arm_cc), indent=2))
