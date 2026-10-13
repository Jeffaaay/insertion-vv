# C1 sealed SIL predictions for later hardware comparison

The prospective prediction sentences remain unchanged in C1_PREREG.md (including
amendment A1), committed before any Phase C run. This file seals observed SIL
outcomes; it does not revise the preregistration or claim hardware confirmation.

- Matrix: `artifacts/c1/matrix.json`
- SHA-256: `cc833c35864f0f8cfa4d67671bf605a129c2b18a5f59710be41ee11e2eb98aa9`
- Generating commit: `fdf69d211eed59052e6eae4a302e00d55ab450c3`
- Source inventory, pinned dependencies, C numerical-build hash and full numerical
  platform fingerprint: `artifacts/c1/execution-manifest.json` and matrix metadata.
- Platform: Windows, AMD Ryzen 9 8940HX, Python 3.12.10, MuJoCo 3.8.0, NumPy 2.2.6;
  OMP/OpenBLAS threads=1. These are local Windows results, not canonical Linux data.
- 3,615 logical runs, each executed twice: 2,730 PASS / 789 FAIL / 96 INVALID.
  All 3,615 trace/truth hash pairs match on repetition, including partial INVALID
  traces. 3,519 completed reproducibly. All 1,106 identity assessments pass.
- `artifacts/c1/evidence-audit.json`: all 7,230 gzip files match sealed hashes and
  completed-tick line counts. Total compressed trace/truth size: 3,780,027,191 bytes.
  Full lossless files remain local under `artifacts/c1/runs`; gigabytes are not in git.

## Frozen predictions versus observations

Unsupported predictions first:

- P1: F4=25 Hz FAIL at every onset — **unsupported**: 4/4 PASS.
- P3: F1>=60 ticks FAIL at every onset — **unsupported**: 8/8 PASS.
- P4: transient faults worst at 2.4 s — **unsupported**: RMS worst at 5 s for
  F1/F2/F3; only F6 is worst at 2.4 s. No exact ties.
- P2: F5>=1.6 Hz FAIL — **supported**: 2/2 FAIL; already FAIL at 1.3 Hz.
- P5: no-delay has strictly most flips — **supported**: 280 PASS-to-FAIL flips,
  zero reverse flips; all other ablations have zero flips. No-delay nominal already
  FAILS. This is a fixed-delay estimator interface effect, not evidence that lower
  physical latency worsens tracking. Disabled faults and zero-noise identity cases
  have the registered interpretation; no nuisance noise was introduced.

## Preview baseline severity boundary, pooled over registered onsets/seeds

| Fault | Observed first FAIL | Scope |
|---|---|---|
| F1 frozen frames | None observed | All tested 1–120 ticks PASS |
| F2 dropped frames | None observed | All tested 1–50% PASS |
| F3 jitter | None observed | All tested sigma 0.5–10 ms PASS |
| F4 sample rate | None observed | All tested 1000–25 Hz PASS |
| F5 cardiac drift | 1.3 Hz | Mildest tested drift already FAIL; no preceding tested drift PASS |
| F6 simulated deadline miss | None observed | All tested 1–50 ticks PASS in Python; HIL required |
| F7 force clipping | 50% nominal peak | Preceding 100% PASS; 50/25/10% FAIL |
| F8 surface quantization | None observed | All tested 24–10 bits PASS |

Nominal preview: PASS, contact RMS 1.1225636065 µm. No nonmonotonic verdict reversals
were observed. These are sampled boundaries, not interpolated physical limits.
Five 300 dpi PNG/SVG figures are in `artifacts/c1/figs`; full derived counts,
per-onset maxima, selected run IDs and both flip directions are in `summary.json`.
The three older Figure 4 controllers already FAIL their nominal cases; their fault
FAIL labels do not establish newly induced failures.

## Precision agreement and explicit coverage gap

There are 1,782 preview/C32 pairs: 1,686 valid, 1,686 matching, 0 disagreeing,
96 invalid pairs. Every invalid pair is F6: the frozen C32 ABI rejects resumed
nonconsecutive tick numbers. C32 has 0/96 valid F6 cases; do not report an unqualified
100% agreement. Error strings and partial evidence are retained. Both controllers
use the Python injector in this matrix. The Rust injector is separately checked
byte-for-byte across all severities, five F2/F3 seeds and both base delays; it is
not a Rust closed-loop or hardware validation.

F9 serial CRC and F10 board/PC clock drift remain HIL-only, with no simulated
PASS/FAIL. Actual ISR lateness and F6 behavior must be measured on hardware.
M3 must verify this seal and use retained traces without new simulation runs.
