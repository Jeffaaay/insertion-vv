"""Build-only H723 firmware from pinned, checksummed ST/ARM sources; never flash."""

import argparse
import concurrent.futures
import hashlib
import json
import re
import shutil
import struct
import subprocess
import urllib.request
from pathlib import Path

from tools.build_controller import ARM_FLAGS, FLAGS, ROOT, digest

MANIFEST = ROOT / "firmware/deps.lock.json"
BOARD = ROOT / "firmware/h723"
MEMORY = {
    "FLASH": (0x08000000, 1024 * 1024),
    "DTCM": (0x20000000, 128 * 1024),
    "AXI": (0x24000000, 320 * 1024),
    "D2": (0x30000000, 32 * 1024),
}


def dependencies():
    manifest = json.loads(MANIFEST.read_text())
    cache = ROOT / ".toolchains/firmware-deps" / digest(MANIFEST)

    def fetch(entry):
        destination = (cache / entry["package"] / entry["path"]).resolve()
        destination.relative_to(cache.resolve())
        if destination.is_file() and digest(destination) == entry["sha256"]:
            return
        if not entry["url"].startswith("https://raw.githubusercontent.com/"):
            raise ValueError("dependency URL must use pinned official GitHub source")
        content = urllib.request.urlopen(entry["url"], timeout=30).read()
        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise ValueError(f"dependency SHA mismatch: {entry['path']}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".download")
        temporary.write_bytes(content)
        temporary.replace(destination)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(fetch, manifest["files"]))
    return cache, manifest


def command(args):
    subprocess.run([str(a) for a in args], check=True, cwd=ROOT)


def build(output, compiler):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("firmware output must be empty; preserve earlier builds")
    compiler = Path(shutil.which(compiler) or compiler).resolve()
    if not compiler.is_file():
        raise ValueError("Arm GNU compiler not found")
    suffix = ".exe" if compiler.suffix == ".exe" else ""

    def tool(name):
        return compiler.with_name("arm-none-eabi-" + name + suffix)

    vendor, manifest = dependencies()
    git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    source_hash = hashlib.sha256(
        (ROOT / "firmware/ctrl/controller.c").read_bytes()
        + b"\0"
        + (ROOT / "firmware/ctrl/controller.h").read_bytes()
    ).hexdigest()
    (output / "build_identity.h").write_text(
        f'#define VV_BUILD_GIT "{git_commit}"\n'
        f'#define VV_CONTROLLER_SOURCE_SHA256 "{source_hash}"\n',
        encoding="ascii",
    )
    includes = [
        BOARD,
        output,
        vendor / "device/Include",
        vendor / "cmsis/CMSIS/Core/Include",
        vendor / "hal/Inc",
    ]
    common = [
        *ARM_FLAGS,
        "-DSTM32H723xx",
        "-DUSE_HAL_DRIVER",
        "-DUSE_PWR_LDO_SUPPLY",
        "-DUSER_VECT_TAB_ADDRESS",
        "-DHSE_VALUE=8000000UL",
        "-ffunction-sections",
        "-fdata-sections",
        "-fstack-usage",
        *(item for path in includes for item in ("-I", str(path))),
    ]
    own = [
        ROOT / "firmware/ctrl/controller.c",
        ROOT / "firmware/protocol/protocol.c",
        ROOT / "firmware/protocol/replay.c",
        BOARD / "main.c",
    ]
    supplied = sorted((vendor / "hal/Src").glob("*.c")) + [
        vendor / "device/Source/Templates/system_stm32h7xx.c"
    ]
    objects = []
    for source in own + supplied:
        obj = output / (source.stem + ".o")
        # Vendor clock calculations intentionally use double precision. The
        # controller always retains every registered arithmetic/warning option.
        flags = FLAGS if source in own else [v for v in FLAGS if v != "-Wdouble-promotion"]
        command([compiler, *flags, *common, "-c", source, "-o", obj])
        objects.append(obj)
    startup = vendor / "device/Source/Templates/gcc/startup_stm32h723xx.s"
    startup_obj = output / "startup.o"
    command([compiler, *ARM_FLAGS, "-c", startup, "-o", startup_obj])
    objects.append(startup_obj)
    elf, binary = output / "insertion-h723.elf", output / "insertion-h723.bin"
    link_flags = [
        *ARM_FLAGS,
        "-nostartfiles",
        "--specs=nano.specs",
        "--specs=nosys.specs",
        "-Wl,--gc-sections",
        "-Wl,--print-memory-usage",
        f"-Wl,-Map={output / 'firmware.map'}",
        "-T",
        str(BOARD / "linker.ld"),
    ]
    command(
        [
            compiler,
            *link_flags,
            *objects,
            "-Wl,--start-group",
            "-lc",
            "-lm",
            "-lgcc",
            "-lnosys",
            "-Wl,--end-group",
            "-o",
            elf,
        ]
    )
    command([tool("objcopy"), "-O", "binary", elf, binary])
    symbols_text = subprocess.check_output([str(tool("nm")), "-n", str(elf)], text=True)
    symbols = {}
    for line in symbols_text.splitlines():
        fields = line.split()
        if len(fields) == 3:
            symbols[fields[2]] = int(fields[0], 16)
    stack_pointer, reset_vector = struct.unpack("<II", binary.read_bytes()[:8])
    if stack_pointer != 0x20020000 or reset_vector != symbols["Reset_Handler"] | 1:
        raise ValueError("invalid boot vectors")
    for handler in ("TIM6_DAC_IRQHandler", "USART3_IRQHandler", "DMA1_Stream0_IRQHandler"):
        if symbols[handler] == symbols["Default_Handler"]:
            raise ValueError(f"unimplemented interrupt: {handler}")
    shim = subprocess.check_output(
        [str(tool("objdump")), "-d", "--disassemble=TIM6_DAC_IRQHandler", str(elf)], text=True
    )
    (output / "irq_entry_disassembly.txt").write_text(shim)
    instructions = re.findall(r"^\s*[0-9a-f]+:\s+(?:[0-9a-f]{4}\s+)+([^\n]+)", shim, re.M)
    if (
        len(instructions) != 3
        or not re.match(r"ldr\s+r0, \[pc,", instructions[0])
        or not re.match(r"ldr\s+r0, \[r0", instructions[1])
        or "<tim6_body>" not in instructions[2]
    ):
        raise ValueError("IRQ entry must sample DWT before a C prologue")
    if any(name in symbols for name in ("malloc", "_malloc_r", "calloc", "realloc")):
        raise ValueError("unexpected dynamic allocator linked into firmware")
    attributes = subprocess.check_output([str(tool("readelf")), "-A", str(elf)], text=True)
    (output / "arm_attributes.txt").write_text(attributes)
    if "Tag_ABI_VFP_args: VFP registers" not in attributes:
        raise ValueError("firmware did not link with hard-float ABI")
    sections_text = subprocess.check_output([str(tool("objdump")), "-h", str(elf)], text=True)
    (output / "sections.txt").write_text(sections_text)
    sections = {}
    for line in sections_text.splitlines():
        match = re.match(r"\s*\d+\s+(\S+)\s+([\da-f]+)\s+([\da-f]+)\s+([\da-f]+)\s+", line)
        if match:
            name, size, vma, lma = match.groups()
            sections[name] = {"size": int(size, 16), "vma": int(vma, 16), "lma": int(lma, 16)}
    memory = {}
    for name, (base, capacity) in MEMORY.items():
        allocations = [s for s in sections.values() if base <= s["vma"] < base + capacity]
        section_bytes = sum(s["size"] for s in allocations)
        used = max((s["vma"] + s["size"] - base for s in allocations), default=0)
        if name == "FLASH":
            used = max(used, sections[".data"]["lma"] + sections[".data"]["size"] - base)
        if name == "DTCM":
            used = symbols["_dtcm_used_end"] - base + sections[".stack"]["size"]
        if used > capacity or any(s["vma"] + s["size"] > base + capacity for s in allocations):
            raise ValueError(f"memory overflow: {name}")
        memory[name] = {
            "base": hex(base),
            "capacity_bytes": capacity,
            "allocated_bytes": used,
            "unallocated_bytes": capacity - used,
            "section_bytes_with_vma_in_region": section_bytes,
        }
    if sections[".replay_inputs"]["size"] != 256000 or sections[".telemetry"]["size"] != 104000:
        raise ValueError("incomplete replay memory reservation")
    if sections[".replay_timing"]["size"] != 64000:
        raise ValueError("incomplete replay timing breakdown")
    if sections[".stack"]["size"] != 16384 or sections[".dma"]["vma"] != 0x30000000:
        raise ValueError("invalid stack/DMA placement")
    licenses = output / "licenses"
    licenses.mkdir()
    for entry in manifest["files"]:
        if entry["path"].startswith("LICENSE"):
            shutil.copyfile(
                vendor / entry["package"] / entry["path"], licenses / (entry["package"] + ".txt")
            )
    libm = Path(
        subprocess.check_output(
            [str(compiler), *ARM_FLAGS, "-print-file-name=libm.a"], text=True
        ).strip()
    )
    report = {
        "stage": "B2.1-build-only",
        "status": "PASS",
        "hardware_measured": False,
        "git_commit": git_commit,
        "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
        "compiler": subprocess.check_output([str(compiler), "--version"], text=True).strip(),
        "controller_source_sha256": source_hash,
        "controller_flags": FLAGS + common,
        "vendor_flags": [v for v in FLAGS if v != "-Wdouble-promotion"] + common,
        "link_flags": link_flags,
        "libm_archive_sha256": digest(libm),
        "vendor_manifest_sha256": digest(MANIFEST),
        "vendor_packages": manifest["packages"],
        "sources": {
            p.relative_to(ROOT).as_posix(): digest(p)
            for p in [
                *own,
                BOARD / "stm32h7xx_hal_conf.h",
                BOARD / "linker.ld",
                ROOT / "firmware/ctrl/controller.h",
                ROOT / "firmware/protocol/protocol.h",
                ROOT / "firmware/protocol/replay.h",
            ]
        },
        "elf_sha256": digest(elf),
        "binary_sha256": digest(binary),
        "binary_bytes": binary.stat().st_size,
        "irq_entry_shim_verified": True,
        "sections": sections,
        "memory": memory,
        "dtcm_gap_before_stack_bytes": symbols["_stack_limit"] - symbols["_dtcm_used_end"],
        "boot_vectors": {"stack_pointer": hex(stack_pointer), "reset_vector": hex(reset_vector)},
        "configured_hardware": {
            "board": "NUCLEO-H723ZG",
            "core_hz": 520000000,
            "timer_hz": 260000000,
            "hse_bypass_hz": 8000000,
            "tim6_prescaler": 259,
            "tim6_period": 999,
            "control_period_us": 1000,
            "uart": "USART3 PD8/PD9 AF7",
            "baud": 460800,
            "framing": "8N1",
            "rx_dma": "DMA1 Stream0 circular, DMAMUX request 45, D2 SRAM",
            "instruction_cache": True,
            "data_cache": False,
            "fpu": "fpv5-d16 hard ABI; FPSCR=0",
            "replay_implemented": True,
            "lockstep_capability_only": False,
            "replay_cpu_sleep": False,
            "mode_exclusivity": (
                "TIM6 IRQ/UIE disabled outside replay; UART/DMA IRQs disabled during replay; "
                "runtime register assertions"
            ),
            "stack_watermark": "boot paints unused prefix below MSP minus 256 bytes",
            "instrumentation_gpio": "PG2 / ZIO D49 / CN8 pin 14; 3.3 V ISR body pulse",
        },
    }
    (output / "build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"status": "PASS", "memory": memory, "elf_sha256": report["elf_sha256"]}, indent=2
        )
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--arm-cc", required=True)
    args = parser.parse_args()
    build(args.output, args.arm_cc)
