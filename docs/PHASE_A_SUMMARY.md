# Phase A: simulation baseline and verification closeout

This phase establishes a usable controller and a reproducible test stack for the
later STM32 comparison. It reproduces paper-scale behavior with documented choices;
it does not claim the author's unpublished MPC implementation or clinical fidelity.

## Controller results

Canonical Linux, seed 42, measured 16 N/m primary contact, 1 ms physics/control,
15 ms sensing delay. Free window 1–2 s; contact window 3–8 s. The task contract is
contact RMS <20 µm, peak absolute relative error velocity <2 mm/s, no safety stop.

| Controller | Our free/contact RMS (µm) | Paper free/contact RMS (µm) | Our verdict |
| --- | ---: | ---: | --- |
| lab_frame_pd | 270.369 / 256.592 | 286.1 / 275.5 | FAIL |
| delayed_feedback | 19.310 / 184.431 | 18.3 / 176.8 | FAIL |
| delayed_feedback_offsetfree | 19.301 / 20.631 | contact 30.3 (offset-free ablation) | FAIL |
| preview | 2.709 / 1.123 | 12.0 / 1.9 (preview MPC) | PASS |

Paper comparisons refer to [v1 HTML Table IV](https://arxiv.org/html/2608.08860v1)
except the offset-free row (Table XII, 30-seed QP ablation). Our four rows use one
seed and PD; controller, aggregate and setup differences preclude numerical ranking
against the paper. The 3.5 N/m diagnostic preview also passes with 7.350 µm contact
RMS, although diagnostic PASS was not required. Primary preview peak contact force
is 4.853 mN, error velocity 0.0727 mm/s; this simplified controller has no force QP.

Each optional step changes one component. Step 1 adds the position-encoder
acceleration-bias observer. Step 2 keeps that observer and PD unchanged, adding a
known-frequency (1.2/2.4/0.25 Hz) measured-surface Kalman predictor. Amplitudes and
phases are estimated; no truth or force readback reaches the controller. One
numerical adjustment changed Joseph covariance arithmetic to square-root QR without
tuning model/controller parameters. Details and every attempt are preserved in
[REPLICATION_NOTES](REPLICATION_NOTES.md).

## Three findings

1. Paper versions disagree about actual MuJoCo contact stiffness versus the
   16 N/m force-constraint model; calibrating the plant matters. Our 3.5 N/m
   diagnostic reduces force but its lab-frame peak 4.708 mN misses the original
   2–4 mN hypothesis. That result was retained without fitting.
2. Windows/Linux first differ by one ulp at delivered trace t=0.351 s
   (2.71e-20 m). Each is internally deterministic; universal cross-OS SHA was too strict.
3. The old five-field fingerprint groups different CPU/BLAS environments.
   Preview exposes cross-machine rounding and early covariance conditioning.
   Square-root arithmetic fixes tolerance amplification; fuller provenance fixes
   comparison classification. Specific dispatch causality remains an inference.

The versioned evidence, arithmetic and limitations are in [FINDINGS](FINDINGS.md).

## Determinism and CI

Every run records source/config/seed and a v2 full numerical-platform fingerprint:
OS/release/build, architecture, CPU model and detected ISA flags, Python/MuJoCo/NumPy,
and BLAS/LAPACK build/runtime/dispatch/thread count. No hostname or install path is
part of the fingerprint. Same full fingerprints demand exact trace/truth SHA;
different full fingerprints use positions <1e-12 m, velocities <1e-9 m/s, forces
<1e-12 N, metric relative difference <1e-9 and identical discrete fields/verdicts.
Legacy v1 pairs remain under their historical rules; v1/v2 pairs require fresh runs.

The preview checkpoint passed 162 tests per OS, eight experiments per OS and eight
Linux/Windows comparisons in [run 38321802925](https://github.com/Jeffaaay/insertion-vv/actions/runs/38321802925).
B0 passes **170 tests in each of local Windows, hosted Windows and Linux** in
[run 38322571543](https://github.com/Jeffaaay/insertion-vv/actions/runs/38322571543).
All eight Linux/Windows comparisons and all eight local/hosted Windows comparisons
pass; the latter correctly use different-platform tolerances. All old-controller
regression anchors remain exact. Local and Linux preview traces are unchanged;
the fresh Windows runner now reproduces local preview SHA rather than the earlier
runner's SHA. Old missing CPU metadata is not backfilled. `v0.1-phase-a` marks this
closeout plus its documentation. Plots/videos remain outside CI.

| Full fingerprint component | Local Windows | Fresh hosted Windows |
| --- | --- | --- |
| OS release / build | 10 / 10.0.19045 | 2022Server / 10.0.20348 |
| CPU | AMD Ryzen 9 8940HX | Intel Xeon Platinum 8573C |
| AVX2 / AVX512F / FMA3 | yes / yes / yes | yes / yes / yes |
| BLAS/LAPACK | OpenBLAS 0.3.29 | OpenBLAS 0.3.29 |
| Runtime dispatch / threads | SkylakeX / 1 | SkylakeX / 1 |
| Python / MuJoCo / NumPy | 3.12.10 / 3.8.0 / 2.2.6 | same |

Complete flags and build strings are preserved in every run and
`artifacts/release/phase_a_closeout.json`; no numeric code or tolerance changed.
The fresh Windows pair happens to have identical traces. This does not justify
inventing CPU/BLAS metadata for the older mismatching runner.

## Targets for later fault injection

Two observed transient intervals deserve explicit Phase C campaigns:

- 0–0.5 s: startup as the harmonic estimator acquires the signal from zero state.
- 2.3–2.6 s: contact entry while the bias observer adapts to newly applied force.

These intervals are outside the scored contact window and do not prove a failure
will escape a later contract. The diagnostic's contact-entry oscillation also
extends just past 3 s. Whole-run plots retain all transients. Future tests should
register timing and verdict rules before injecting faults at these points.

## Hardware boundary

No hardware result is claimed by Phase A. NUCLEO-H723ZG ownership is confirmed;
the user initially reports the board is not connected. Phase B will verify actual
firmware, protocol integrity and timing, with independently registered tolerances.
Known fixed frequencies and nominal noiseless 1 kHz measurements in this table do
not establish robustness to drift, quantization, firmware jitter or float32.
