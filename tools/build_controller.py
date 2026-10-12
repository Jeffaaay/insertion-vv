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
    (output / "build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cc")
    parser.add_argument("--arm-cc")
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.cc, args.arm_cc), indent=2))
