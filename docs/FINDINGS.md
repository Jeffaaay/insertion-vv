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
