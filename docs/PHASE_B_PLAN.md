# Phase B implementation and preregistration

Registered before the first C32 experiment. Phase A is frozen at `v0.1-phase-a`;
MuJoCo and its sensor/evaluator code remain the plant for all backends. The new
variable is the controller implementation: Python binary64, portable C binary32,
then that same C on STM32. This is development-board HIL, with no physical actuator.

## B1 checkpoints

1. Portable C11 controller: identical PD, bias-observer equations, seven-state
   square-root Kalman model and parameters. Fixed arrays, no heap/platform headers.
   Householder QR implements the same root update without a BLAS dependency.
   Compile host library and Cortex-M7 object, run independent numerical/API tests.
2. Python C32 adapter: primary and paper_effective, seed 42, 8000 ticks, two repeats.
   Compare against frozen Python preview. Primary must retain nominal PASS, contact
   RMS within 5% of 1.1225636065319848 µm, and maximum absolute needle-position
   difference across all ticks <1e-7 m. Diagnostic metrics are reported without
   fitting. Report max/RMS position, velocity and command/contact-force deltas.
3. Register framed little-endian CRC16 protocol, including every controller input.
   The review's abbreviated frame omitted needle velocity and measurement capture
   time/sequence; retaining them avoids changing PD or fresh/held measurement logic.
4. Rust 1.99 / edition 2024 harness: separate Plant and Controller traits. Python
   MuJoCo subprocess; C FFI and serial controller backends. On the same host build,
   C32 ctypes and Rust FFI must produce bitwise-identical traces and truth.
5. Host virtual board through the same framed transport codec over loopback TCP;
   require bitwise equality with FFI. This tests framing, not UART hardware timing.
6. H723 build-only firmware with USART3/ST-LINK VCP, RX DMA, TIM 1 kHz and DWT.
   Lockstep replies per sensor frame; replay timing implementation follows in B2.

Each checkpoint commits separately, runs local checks and hosted CI, and leaves
Phase A numerical files unchanged. Report checkpoint 2 and checkpoint 6 to Claude,
then continue the user's scoped review/implementation loop. A failed numerical
gate is evidence to diagnose and report, never permission to tune gains/noise.

## Separate contracts

The Phase A binary64 cross-platform thresholds remain unchanged. Phase B gets its
own report and contract: it must not be smuggled into the four-controller Phase A
matrix or judged using inappropriate binary64 tolerances. Output trace/metric field
names remain compatible; the existing comparator can check same-build backend
equivalence directly, while float32-vs-float64 uses an explicit separate comparison.

Same complete host/build fingerprint + same C32 inputs: exact repeat SHA required.
Host ctypes/FFI/virtual-board paths use the same C build and input quantization.
Across C32 numerical platforms, pre-register position <1e-7 m, velocity <1e-5 m/s,
force <1e-6 N, physical metric relative difference <0.05 and identical verdicts.
These are engineering equivalence budgets, not claims about measured errors.
Float64-vs-C32 additionally uses the primary magnitude gate above. Missing frames,
bad CRC, wrong tick, nonfinite inputs/outputs, timeout or incomplete duration yield
INVALID; an intact trajectory outside the task specification yields FAIL.

Strict arithmetic: binary32 C constants/functions, no fast-math, FMA contraction
off, `-O2 -ffp-contract=off -fno-fast-math`. These options reduce arithmetic
differences but do not guarantee host/ARM libm equality. Board firmware provenance
must include compiler, flags, ELF digest, clock and FPU configuration.

## B2 preregistered timing and hardware targets

- Functional lockstep: both contact profiles, seed 42, same inputs/controller,
  C32 comparison budgets above, identical verdict, complete framing evidence.
- Board replay: 8000 saved sensor frames, TIM-driven 1 kHz, measured computation
  p99 <100 µs and zero 1 ms deadline misses; publish p50/p95/p99/max computation
  and interrupt-period jitter with cycles-to-time clock provenance.
- Same board binary/input stream: replay command bits equal board lockstep bits.
- A positive functional lockstep result is not a wall-clock real-time result.
  UART wire time and USB/OS latency must be measured separately. No assumed 1 ms
  USB latency is substituted for a measurement. No hardware success before a
  detected, identified, flashed board and recorded actual runs.

The user owns NUCLEO-H723ZG but initially reports it disconnected. Software work
continues independently. Frequency adaptation and full Phase C fault campaigns
remain future work, outside these Phase B checkpoints.
