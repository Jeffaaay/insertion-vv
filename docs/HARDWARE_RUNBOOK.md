# NUCLEO-H723ZG hardware runbook

This is an execution procedure, not a report of a board experiment. B2.1 firmware
and B2.2 host tools retain the frozen Phase A plant and portable C32 controller.
The preregistered gates and measurement boundaries are in
[PHASE_B_HARDWARE_PLAN.md](PHASE_B_HARDWARE_PLAN.md). All commands run at repo root.
Each output directory must be new. Preserve failures; do not overwrite evidence.

## Build and prepare

Use the pinned Python dependencies and Rust 1.99.0 as in CI. `cargo build --release`
builds both `insertion-harness` and `board-link`. The Windows executables have `.exe`
suffixes. Linux uses the same commands without these suffixes.

```powershell
python -m pip install -r requirements-lock.txt
cargo +1.99.0 build --manifest-path harness/Cargo.toml --locked --release
python -m tools.build_controller --output artifacts/hardware/host-build
python -m tools.board prepare --run <SUCCESSFUL_PHASE_B_RUN_ID> --output artifacts/hardware/prepared
```

The prepare command accepts only a completed green Phase B run on this repository's
`main`. It downloads the H723 image plus canonical Linux C32 evidence, verifies the
BIN/ELF and local source hashes, and records the CI URL/commit. Use a clean checkout
of that commit for execution. No board is needed to prepare. No GitHub secrets or
repository settings are required beyond ordinary artifact download access.

## Connect, identify and preserve

Connect the Nucleo **ST-LINK CN1 Micro-USB port with a data cable**. No actuator is
used. Select the actual ST-LINK serial and its VCP port from device enumeration;
do not assume a COM number or select an unrelated serial device.

```powershell
harness/target/release/board-link.exe --list-ports
python -m tools.board identify --openocd <OPENOCD_EXE> --scripts <OPENOCD_SCRIPTS> --probe <STLINK_SERIAL> --output artifacts/hardware/identify
python -m tools.board flash --openocd <OPENOCD_EXE> --scripts <OPENOCD_SCRIPTS> --probe <STLINK_SERIAL> --firmware artifacts/hardware/prepared/firmware --output artifacts/hardware/flash
```

OpenOCD 0.12.0 uses `interface/stlink.cfg`, `dapdirect_swd` and `target/stm32h7x.cfg`.
Identification resets/halts and resumes the board, reads MCU family/CPUID, 96-bit
UID, Flash size and option status. It requires H72x/H73x Cortex-M7, 1 MiB Flash and
unprotected RDP Level 0. A different family, invalid UID, protection or a failed
read stops execution. No option-byte writes/unlock commands are performed.

Before programming, the tool saves the full original 1 MiB Flash and its SHA locally.
UID is checked again in each backup/program connection. Programming erases only
image-covered sectors, verifies the image and independently dumps its bytes for
SHA comparison. Retain the original backup locally; **never attach it to Claude or
commit/upload it**. `flash_receipt.json` binds image, ELF, CI origin, readback and
board identity; it does not claim numerical or timing success. Runtime INFO and
Flash CRC32 must subsequently match that receipt before an experiment proceeds.

## Lockstep first, then independent 1 kHz replay

Run `primary` first, inspect the report, then `paper_effective`. Replace all
placeholders with observed paths/port. This command performs two real serial
8000-tick closed-loop runs with seed 42, preserving trace, truth and raw wire logs.
MuJoCo advances only after a valid board command. The 200 ms UART transaction
deadline measures availability; USB lockstep is not the real-time timing test.

```powershell
python -m harness.hardware lockstep --firmware artifacts/hardware/prepared/firmware --receipt artifacts/hardware/flash/flash_receipt.json --port <COM_PORT> --board-link harness/target/release/board-link.exe --executable harness/target/release/insertion-harness.exe --host-build artifacts/hardware/host-build --reference artifacts/hardware/prepared/linux-reference/primary/preview_c32 --contact-profile primary --output artifacts/hardware/primary-lockstep
python -m harness.hardware replay --firmware artifacts/hardware/prepared/firmware --receipt artifacts/hardware/flash/flash_receipt.json --port <COM_PORT> --board-link harness/target/release/board-link.exe --lockstep artifacts/hardware/primary-lockstep --output artifacts/hardware/primary-replay
```

Use `paper_effective` in the reference path, profile and output directories for
the second profile. Stop on a functional FAIL/INVALID before replay or the next
profile; do not tune the controller. Reports return 0 PASS, 1 FAIL, 2 INVALID.

Lockstep checks same-board input/output bits and trace/truth SHA repeats, all
existing cross-C32 tolerances and contact RMS relative difference <1% against the
downloaded Linux reference. Raw wire extraction independently checks every CRC,
session, HELLO identity, timestamp, quantized sensor value, command and FINISH ACK.
It produces the exact 232000-byte recorded input stream; no host-generated input
substitution is allowed for the real timing experiment.

Replay uploads 29-byte input records with checked ACKs and complete RAM CRC32,
then START. The host stays quiet for 8.1 s while the board executes TIM6 at 1 kHz;
it fetches all command/timing records with CRC32s afterward. No silent retries.
Every force bit must match this same binary's lockstep output. The independent
Python analysis handles DWT wrap and audits absolute scheduled deadlines. Valid
data exceeding timing gates is FAIL; corrupt, incomplete or inconsistent data is
INVALID. Raw logs and partial results are preserved in either case.

Optional plotting uses the separate visualization environment and is never a CI
dependency:

```powershell
python -m tools.plot_timing artifacts/hardware/primary-replay --output artifacts/viz/hardware_primary_timing.png
```

## Evidence and limits

Keep CI origin/build manifest, Flash receipt/readback, actual board INFO, raw wire
logs, both lockstep traces/truth, input/force bit streams, replay records, metrics
and timing reports. Report UART round-trip distribution separately from ISR compute,
entry-to-control latency and measured ISR body. The body excludes its final
sample/store, GPIO clear and exception epilogue. Stack watermark is conservative.
Compute p99 <100 µs, |period jitter| p99 <5 µs, zero misses/UIF overruns and untouched
stack >=4096 bytes must all pass. Do not infer these from build/static stack reports.

Absolute clock accuracy remains **UNVERIFIED**: DWT and TIM6 share the oscillator,
and USB elapsed time includes host scheduling/poll delay. PG2 (ZIO D49, CN8 pin 14)
is a 3.3 V ISR instrumentation output for an independently calibrated instrument;
it is not an actuator drive. Record any later instrument model, calibration and
capture separately. Only actual successful functional/timing experiments support
a Phase B hardware summary and tag; synthetic CI tests never do.
