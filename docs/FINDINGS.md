# Findings

## Finding #1 — Paper contact-stiffness inconsistency

The [v1 HTML](https://arxiv.org/html/2608.08860v1) and
[v1 PDF](https://arxiv.org/pdf/2608.08860v1) describe approximately 16 N/m plant
contact stiffness. The later [v3 PDF](https://arxiv.org/pdf/2608.08860v3), §VIII-A,
discloses approximately 3 N/m measured quasi-static effective stiffness, not
calibrated to the 16 N/m used by its force-constraint model. Preview headline
numbers also change: 1.9 µm / 3.43 mN in v1 versus 1.1 µm / 1.47 mN in v3.
This is a version-dependent discrepancy, not inherently PDF versus HTML.

Our primary plant is calibrated to 16.000 N/m; a diagnostic `paper_effective`
plant measures 3.500 N/m. With identical lab-frame PD gains and seed 42, primary
contact RMS/peak force are 256.592 µm / 13.283 mN; the diagnostic gives
262.055 µm / 4.708 mN. No tuning followed the diagnostic. At the primary force
peak, 16 N/m × 745.289 µm = 11.925 mN, explaining most of the force magnitude.
The diagnostic's static force estimate at its own peak is 2.264 mN, below the
measured 4.708 mN; dynamics and unchanged contact damping still matter.

**Implication:** a parameter quoted in a constraint model does not establish the
effective stiffness of the simulated plant. Calibrate the actual contact, retain
both declared configurations, cite paper versions, and avoid fitting missing
author settings to a table. This evidence does not prove how every original
table value was generated. [Replication notes](REPLICATION_NOTES.md) retain
sources, full parameter inventory and the unsuccessful bounded code/MJCF search.

## Finding #2 — Cross-platform last-ulp divergence

At baseline commit `24e4dd4`, the original [Windows run](https://github.com/Jeffaaay/insertion-vv/actions/runs/38309462614)
and [Linux run](https://github.com/Jeffaaay/insertion-vv/actions/runs/38315698883)
each passed **43 tests**, and each platform reproduced its own trace SHA-256
exactly. Python 3.12.10, MuJoCo 3.8.0, NumPy 2.2.6, source and configuration
hashes matched. The cross-OS hashes did not:

| Profile | Windows SHA-256 | Linux SHA-256 |
| --- | --- | --- |
| primary | `66422ccb08f67fe12d37936578bae832bf5b9a3d8fd73b357e82b1861ff118a2` | `8554b8902cfa3f231659f2c94b0ab51591dbd0ae60cd3b6b5e91acaab4d03b7f` |
| paper_effective | `cc7e3e7e556c7719c6ff37ac3f2b1581179f286d8ccf452838acac02e5a8998d` | `9faa9e781f2bf0146906f88246f2e1e76b781fc23813291b14be4abc1a04ca7d` |

Both first differ at **trace tick 351 (t=0.351 s)** in the delayed measured
surface position: Windows `0.0002174455954359589` m, Linux
`0.00021744559543595892` m. The difference is **2.710505431213761e-20 m**, one
binary64 ulp at that magnitude. The measurement's capture time is 0.336 s,
15 ms before arrival; 0.351 s is the first observed trace divergence, not the
time of a separately isolated `sin()` call.

Accepted diagnosis: legitimate platform `libm` last-ulp rounding in the
sinusoid-driven plant, not a controller defect. Artifact comparison demonstrates
the rounding-sized discrepancy and internal repeatability; it does not separately
isolate every compiler/libm/solver operation. Across the complete traces the largest
position difference is 5.421e-20 m, velocity difference 1.779e-17 m/s, and command
force difference 2.776e-17 N. Primary contact peak error velocity differs by
4.441e-16 mm/s; the reported RMS and force values are unchanged at the displayed
precision. Both task verdicts remain FAIL.

### Why the old gate was too strict

SHA-256 detects any changed byte, including a final printed floating-point digit.
Same-platform replay checks causality, seeded randomness and repeatability. Using
Windows' hash as a universal Linux reference additionally demands identical
numerical implementations, which the stated physical verification goal does not
require. Passing same-seed replay never implied all OS/CPU combinations were bitwise
equivalent. No sine implementation or stored trace is patched or rounded.

### Two-tier correction

This is the historical first contract; Finding #3 extends its platform identity
to the full v2 fingerprint without changing any numeric tolerance.

- **Intra-platform:** same OS, normalized architecture, Python/MuJoCo/NumPy versions,
  source, config and seed require identical trace and truth SHA-256. Every run stores
  that fingerprint. Replay and independent-process tests enforce equality;
  historical reference hashes apply only to their registered fingerprint.
- **Cross-platform:** all trace and truth positions require |Δ| <1e-12 m, velocities
  <1e-9 m/s, and forces <1e-12 N. Discrete fields/timestamps and full verdicts must
  match. Physical metrics require symmetric relative difference <1e-9. Both-zero
  metrics have relative difference zero; one-zero pairs have difference one.
  Wall-time and run UUIDs are excluded. Invalid/missing/corrupt inputs cannot pass.
  Linux and Windows artifact jobs feed an independent comparison job covering both
  controllers and both contact profiles.

Linux x86_64 is canonical for reported numerical results. Cross-platform tolerance
success and task PASS are distinct: an inadequate baseline can reproducibly FAIL
the task while the verification CI passes.

### Phase B implication

STM32 single precision has machine epsilon 2^-23 ≈ **1.19e-7 relative**, so the
rounding gap is expected to widen toward that scale and may accumulate over time.
This is not a measured HIL result, a fixed 1e-7 m position error, or a guaranteed
trajectory error bound. Phase B will use the tolerance tier for SIL/HIL comparisons,
with unit-specific limits and a metric budget registered before experiments.
The current binary64 SIL limits are unchanged and are not automatically suitable
for single precision, quantization or real timing jitter.

## Finding #3 — Coarse platform identity and covariance conditioning

The optional preview controller introduced NumPy Kalman linear algebra. At
`02ef8e4`, local Windows 10 and hosted Windows Server 2022 shared the original
Windows/x86_64/Python 3.12.10/MuJoCo 3.8.0/NumPy 2.2.6 fingerprint and matching
source/config/seed, yet their preview trace and truth SHA-256 values differed.
All three earlier controllers remained bitwise unchanged. Each environment's
independent-process and same-run repeats remained exact. The largest local/hosted
Windows discrepancy was 1.9516e-17 m, 8.7734e-16 m/s, 1.0978e-16 N; maximum
metric relative difference was 3.02333e-13, with identical verdicts.

NumPy delegates linear algebra to BLAS/LAPACK, whose runtime CPU dispatch is absent
from the old fingerprint. Local inspection reports an AMD Ryzen 9 8940HX,
AVX2/AVX-512/FMA3 support, OpenBLAS 0.3.29 and selected `SkylakeX` kernel. The kernel
name is a dispatch implementation, not a claim the processor is an Intel CPU.
This supports the platform linear-algebra explanation; it does not isolate a
particular QR instruction or prove CPU dispatch alone caused every different bit.
See [NumPy runtime provenance](https://numpy.org/doc/2.2/reference/generated/numpy.show_runtime.html).

There was a separate amplification issue: the first Joseph covariance form had
initial condition numbers about 1.9e7 and Linux/Windows free RMS relative drift
1.5351e-8, exceeding the 1e-9 metric limit. The single allowed adjustment used QR
square-root covariance arithmetic with **identical P0/Q/R, state equations and
control gains**. Maximum cross-platform metric difference fell to 6.59754e-13.
Both original and corrected versions passed nominal task performance. This was a
numerical representation correction; no threshold, sine function or trace was changed.

The B0 contract now records OS release/build, CPU model, detected ISA flags, and
BLAS/LAPACK build/runtime dispatch/thread count in a versioned full fingerprint.
Equal full fingerprints require bitwise equality; different ones use the unchanged
physical tolerances and exact verdicts. Old artifacts are not retroactively amended.
Fresh local/hosted comparison results and both fingerprints belong in the closeout
record. A missing fingerprint field or mixed metadata schema cannot silently pass.

Float32 has much less precision than binary64 (epsilon about 1.19e-7 versus
2.22e-16). Ill-conditioning is therefore more consequential for Phase B, but the
epsilon ratio does **not** establish an actual HIL error multiplier or guarantee
that square-root filtering will meet MCU timing/accuracy requirements. Those need
measurement with a preregistered HIL error budget.

### Fresh full-fingerprint observation

B0 [run 38322571543](https://github.com/Jeffaaay/insertion-vv/actions/runs/38322571543)
passes all comparisons with 170 tests per environment. The fresh Windows runner
is an Intel Xeon Platinum 8573C / Server 2022; local is AMD Ryzen 9 8940HX /
Windows 10. Both report OpenBLAS 0.3.29, `SkylakeX` dispatch and the same detected
AVX2/AVX-512/FMA3 flags. In this fresh pairing, all eight traces are actually
bitwise equal despite the correctly different full fingerprints. The old hosted
Windows preview hashes differ from this new runner, while local and Linux hashes
are unchanged. The prior v1 artifact lacks CPU/dispatch metadata, so we cannot
assert which specific historical feature caused the old mismatch. This observation
supports retaining runtime provenance and explicitly limits the causal claim.
## Follow-up evidence after the B0 tag

The final tag CI [38322919394](https://github.com/Jeffaaay/insertion-vv/actions/runs/38322919394)
ran Windows on AMD EPYC 7763 (AVX512F absent; OpenBLAS Haswell), whereas the preceding
code CI used Xeon 8573C (AVX512F present; SkylakeX). With unchanged numerical source,
the tag runner reproduces the older Windows preview SHA `2b37e3ae...`. Both profiles
remain within the unchanged tolerances, with maximum differences 1.95156e-17 m,
8.77336e-16 m/s and 1.09775e-16 N. The full v2 fingerprint correctly chooses the
cross-platform tier. All three older controllers remain exact, and both jobs pass
170 tests. This is a measured association between dispatch/platform and rounding;
it is not an experiment isolating dispatch as the only cause. The earlier v1 run
still has no recoverable CPU metadata.
## Finding #4 — Nominal C32 precision reference for F8

Before hardware, the portable C32 controller was compared with Python preview on
both contact profiles, seed 42. Canonical Linux primary maximum needle-position
difference is 1.71782082924e-8 m, full-run RMS difference 3.42763844255e-9 m.
Contact RMS differs by 0.05087935%; both profiles retain PASS. No controller
parameter was tuned. Full max/RMS position, velocity and force deltas are recorded
in REPLICATION_NOTES and the B1.2 evidence JSON.

This is the nominal F8 precision reference for later experiments, sometimes called
a quantization floor in the review. It is **not a universal lower/upper error
bound**: the port also changes QR arithmetic order and libm calls, and different
inputs/conditioning/compilers can change accumulated rounding. A later hardware
gap above 0.02 µm cannot, by itself, rule out precision. Phase C must compare the
same inputs and build against this measured reference and the preregistered budget.


## Finding #5 — Registered sensor disruptions can pass with very different margins

Local Windows Phase C preview baseline keeps PASS for F1 through 120 frozen ticks,
F2 through 50% probabilistic loss, F3 through sigma=10 ms, F4 down to 25 Hz, F6
through 50 skipped Python calls, and F8 down to 10 bits. This contradicts registered
P1/P3 and does not imply that the faults have no effect. F1 reaches 13.3184649 µm
contact RMS, leaving 6.6815351 µm to the strict 20 µm limit. Its maximum is at 5 s
injection, versus 4.7631422 µm at 2.4 s, a material counterexample to P4. F2/F3 timing
maxima are formally at 5 s but nearly flat. Maximum absolute changes in contact RMS
from nominal across F2/F3/F8 are 2.5177/8.2104/3.3151 nm. These are metric changes,
not instantaneous position bounds or evidence of universal fault tolerance.

## Finding #6 — Frequency mismatch fails at the mildest registered drift

With the predictor frozen at its original frequencies, phase-continuous actual
cardiac drift from 1.2 to 1.3 Hz already produces FAIL (52.6838745 µm contact RMS).
All larger registered drift targets also FAIL, supporting P2. The experiment
identifies the first tested failing drift, not a continuous physical threshold:
there is no preceding tested drift level that passes. The nominal run passes.
This is evidence within the specified periodic plant and scoring window, pending
comparison with hardware using the same registered inputs and unchanged controller.

## Finding #7 — A structurally supported ablation prediction has limited information

No-delay produces 280 PASS-to-FAIL flips and no reverse flips versus matched preview
baseline. Its 297 runs, including nominal, all FAIL. The original estimator checks
sample_time+15 ms <= current_time; zero-age frames violate that interface contract.
Thus P5 is supported under its exact counting rule, but cannot establish that delay
modeling is necessary or that lower physical latency is harmful. Removing injected
jitter, quantization or dropout changes no verdict in this registered range, where
their baseline cases already PASS. No-noise is an intentional identity because the
registered nominal noise is zero. All 1,106 expected trace/truth identities pass.

## Finding #8 — C32 agreement has a measured F6 coverage gap

Among 1,782 Python/C32 pairs, 1,686 valid pairs agree and none disagree. All other
96 pairs are attempted C32 F6 cases rejected by the frozen ABI on nonconsecutive
tick numbers; they remain INVALID with partial traces, never relabeled as task FAIL.
C32 F6 has 0/96 valid coverage. Firmware ISR lateness with successive tick numbering
is a different mechanism and needs HIL measurement. Maximum valid-pair contact RMS
absolute difference is 0.0022464752 µm; maximum relative difference is 0.0733611%
(in a different case). These statistics do not extend the older nominal position
comparison into a universal precision bound. Both full-matrix controllers use the
Python injector; Rust has independent byte-level injector checks, not a closed-loop
hardware or Rust-matrix result.

## Finding #9 — Clipping can leave a quiet but large insertion-depth error

F7 at 50% nominal peak first FAILS after a passing 100% level. For early onsets
(0.2/1.5/2.4 s), 50/25/10% clipping yields contact RMS about 120/210/264 µm while peak
absolute error velocity is only 0.0090917 mm/s. The retained trajectories show a
persistent depth bias, consistent with inadequate static holding force. Late 5 s
clipping also causes transients, so not every F7 failure is exclusively static.
Nominal peak contact force is 4.853382 mN versus peak applied command 5.744376 mN
(about 84.5%). This suggests a holding-force question for HIL; it is not a tested
85% boundary or justification to interpolate the registered 100/50/25/10% grid.
All Phase C findings refer to matrix cc833c35864f0f8cfa4d67671bf605a129c2b18a5f59710be41ee11e2eb98aa9.
