# Replication notes — Phase A

## Scope and comparison policy

Phase A targets **paper-magnitude baseline with documented deviations**, not bit-exact
paper replication. `lab_frame_pd`, `delayed_feedback`, and the separately authorized
`delayed_feedback_offsetfree` ablation and fixed-frequency `preview` are implemented.
The primary plant remains
16 N/m, as specified in PROJECT_BRIEF.md. `paper_effective` is a diagnostic plant,
not a claim to possess the author's MJCF. During the contact-profile experiment,
no controller gains, contact damping, trajectory, sensor settings or verdict thresholds
were tuned after the diagnostic result. The later delayed-feedback checkpoint adds
a separately documented controller while preserving both plants and lab-frame PD.

Unless stated otherwise, paper comparisons mean **arXiv:2608.08860v1, HTML Table IV**:
[fixed-version HTML](https://arxiv.org/html/2608.08860v1).
Avoid unversioned PDF URLs when quoting values. Sources were checked on 2026-10-12.
The application-level same-seed trace hash is required to match within one platform fingerprint;
there is no claim of bitwise equivalence to the author's implementation.
Linux x86_64 (Ubuntu 24.04 runner, Python 3.12.10, MuJoCo 3.8.0, NumPy 2.2.6)
is now the canonical platform for reported numbers. Earlier explicitly marked
Windows checkpoints remain historical evidence. Cross-platform comparisons use
the two-tier contract documented below and in [FINDINGS.md](FINDINGS.md).

## Paper-internal inconsistency: contact stiffness

| Retrieved source | Contact statement | Preview contact RMS / peak force | Evidence |
| --- | --- | --- | --- |
| HTML v1; submitted 2026-08-09 | Plant described as approximately 16 N/m | 1.9 µm / 3.43 mN | §VII-A; Table IV |
| PDF v1, 16 pages | Same approximately 16 N/m statement and headline values as HTML v1 | 1.9 µm / 3.43 mN | [PDF v1](https://arxiv.org/pdf/2608.08860v1), pp. 1, 8–9 |
| PDF v3, 20 pages; revised 2026-09-28 | Measured plant stiffness approximately 3 N/m; not calibrated to the 16 N/m force-constraint model | 1.1 µm / 1.47 mN | [PDF v3](https://arxiv.org/pdf/2608.08860v3), abstract and §VIII-A, pp. 1, 8 |

The [arXiv submission history](https://arxiv.org/abs/2608.08860) dates v2 to 2026-08-16
and v3 to 2026-09-28. The PDF containing the approximately 3 N/m disclosure is **v3,
later than v1**, although it was encountered earlier in the user's research. The
observed discrepancy is version-dependent, not an inherent PDF-versus-HTML difference.
We have verified the disclosure and changed headline values; we have not verified
that unchanged Table IV values across all versions came from the same executable.
The 1.47/3.43 mN values concern preview control, not the lab-frame PD force reference
of 3.26 mN in HTML v1 Table IV.

This evidence supports investigating a plant-versus-force-model mismatch. It does
not prove that stiffness alone accounts for every difference in the original table.
Missing original geometry, damping and PD gains prevent that stronger conclusion.

### Predetermined diagnostic and measured results

Both configurations use the aligned capsule/servo plant. The diagnostic scales only
the first `solref` value by 3.5/16. Its damping entry (-179) and all five `solimp`
values remain unchanged. The 3.5 N/m target was selected by the user before running;
it was not fitted to a force result. There was one diagnostic CLI invocation; the
runner retains its standard deterministic replay. Subsequent CI repeats are checks
of the frozen configurations, not a parameter search.

| Seed 42 result | `primary` | `paper_effective` |
| --- | ---: | ---: |
| `solref` stiffness entry | -2669.3333333333335 | -583.9166666666667 |
| Measured quasi-static stiffness | 16.000 N/m | 3.500 N/m |
| Free RMS error | 270.369 µm | 270.396 µm |
| Contact RMS error | 256.592 µm | 262.055 µm |
| Contact peak absolute error velocity | 2.757 mm/s | 2.846 mm/s |
| Contact peak normal force | 13.283 mN | 4.708 mN |
| Task verdict | FAIL | FAIL |

Calibration uses eight constant motor loads, five seconds settling per load, covering
50–900 µm actual penetration. Loads are selected using target stiffness, but neither
depth nor force is constrained to the target. Measured force balance, settled velocity,
and the fitted stiffness are checked. This extends the previous 50–500 µm calibration
range to cover both trajectories' peak depths, without changing plant parameters.

**The expected 2–4 mN diagnostic force range was not met.** Reducing stiffness
substantially reduces force, but does not fully reproduce the proposed arithmetic.
CI reports that expectation separately from determinism, calibration and task verdict.
The earlier 6.52 mN stop condition for the primary profile was withdrawn by the user;
the primary profile is not retuned or rejected simply for exceeding it.

### Penetration arithmetic and its limits

The commanded component amplitudes sum to 560 µm. With a fixed -300 µm needle
coordinate, 860 µm is a conservative displacement-based upper bound; the sinusoidal
components do not necessarily peak together, and servo dynamics/contact alter motion.

In the primary run, peak force at 5.104 s occurs at 745.289 µm penetration:
16 N/m × 745.289 µm = 11.925 mN, versus measured 13.283 mN. At that same depth,
3.5 N/m would predict 2.609 mN statically. However, changing stiffness changes the
trajectory and time of the force peak, so this is not a prediction of the new peak.

In `paper_effective`, peak force occurs at 5.040 s, at 646.856 µm penetration and
-2.312 mm/s needle-minus-tissue velocity. Its static estimate is 2.264 mN, while the
actual force is 4.708 mN; the 2.444 mN difference reflects dynamic contact/solver
effects, including the unchanged damping. We have not separately identified each
contribution, so it is not labeled a measured damping-only force. Maximum penetration
is 811.896 µm, attained at a different tick. No further tuning was performed.

### History

| Checkpoint | Geometry / tissue servo kp, kv | Contact RMS | Peak force | Interpretation |
| --- | --- | ---: | ---: | --- |
| Initial, commit `6a12700` | Sphere / 1,000,000, 2,000 | 256.2 µm (256.207985) | 12.55 mN (12.552340) | Brief-magnitude baseline; paper servo/shape not aligned |
| Parameter alignment | Capsule / 8,000, 120 | 256.592 µm | 13.283 mN | Stiffness stayed 16 N/m; force stop gate triggered |
| Current primary | Same aligned plant, 16 N/m | 256.592 µm | 13.283 mN | Primary retained by user decision |
| Current diagnostic | Same aligned plant, 3.5 N/m | 262.055 µm | 4.708 mN | Lower force; 2–4 mN expectation not met |

## Parameter inventory

Status vocabulary: `aligned` means matches a stated value or method;
`unknown-in-paper` means our choice is not established by the inspected paper;
`deliberate deviation` means an explicit difference, including diagnostic choices.
Listed numbers refer to the primary profile unless a diagnostic value is shown.
Source shorthand: III = v1 system model; VII = v1 simulation study; B-B = v1 realism
appendix; Brief = PROJECT_BRIEF.md; Choice = this implementation; Decision = user.
We do not infer missing values from output tables.

| Parameter | Paper value / statement | Our value | Source | Status |
| --- | --- | --- | --- | --- |
| MuJoCo version | 3.8 | 3.8.0 | VII; Choice patch pin | aligned |
| Python / NumPy | Not established | 3.12.10 / 2.2.6 | Choice; requirements lock | unknown-in-paper |
| Controllers | Lab-frame PD; delayed-feedback impedance | Both Phase A baselines | VII-C | aligned |
| Lab-frame PD kp / kd | Baseline gains not established | 400 N/m / 0.8 N·s/m | Choice, frozen before first run | unknown-in-paper |
| PD law | Fixed lab-frame tracking | Position + velocity error, time-only reference | VII-C; Choice implementation | aligned |
| Delayed-feedback kp / kd | Baseline gains not established | 10 N/m / 0.2 N·s/m | Choice, frozen before first delayed run | unknown-in-paper |
| Delayed-feedback velocity estimator | Filtered estimate stated; coefficients not established | Backward difference over capture times + backward-Euler low-pass, tau=5 ms | VII-D; Choice coefficients | unknown-in-paper |
| Delayed-feedback position reference | Delayed measured surface, no prediction | Received position + time-only reference gap; no extrapolation | VII-C | aligned |
| Delayed-feedback startup / missing frames | Not established | Surface/velocity zero initially; first arrival initializes position; hold both estimates between frames | Choice | unknown-in-paper |
| Offset-free observer state / measurement | [p,v,a], position only | Same; needle encoder, not surface or force readback | V, Eq. (8) | aligned |
| Offset-free discrete prediction | p+=Ts*v; v+=Ts*(a+u/m); a held | Same; previous commanded force, Ts=1 ms | V, Eq. (8) | aligned |
| Offset-free correction gain L | [0.6,12,400] | Same | V | aligned |
| Offset-free nominal mass | 1 g | 0.001 kg | V, Eq. (8); Table III | aligned |
| Observer initialization | Not established | First measured p, v=0, a=0; no fabricated pre-start step | Choice | unknown-in-paper |
| Bias compensation in controller | Bias enters QP horizon | Subtract m*a from unchanged delayed PD command | User single-variable Step 1; Choice | deliberate deviation |
| Offset-free-only ablation | 30.3±0.2 µm contact, fixed QP, 30 seeds | PD + observer, seed 42, pre-registered 20–40 µm for both profiles | Table XII; user acceptance | deliberate deviation |
| Preview exosystem | DC + cardiac/second harmonic/respiration | Seven states, frequencies 1.2/2.4/0.25 Hz fixed | III-B Eq. (3); user Step 2 | aligned |
| Preview amplitudes / phases | Estimated from delayed surface | Zero initial state; estimated only from received measurements | III-B, V | aligned |
| Kalman initial covariance | Not established for this implementation | (500 µm)^2 I | Choice, pre-registered | unknown-in-paper |
| Kalman measurement variance | Not established for this implementation | (2 µm)^2 | Choice, design variance even in noiseless nominal run | unknown-in-paper |
| Kalman continuous process covariance | Not established for this implementation | (0.2 µm/sqrt(s))^2 I | Choice, multiplied by capture interval in seconds | unknown-in-paper |
| Preview correction / delay handling | Kalman filter, forward propagation by latency | Joseph correction at capture time; propagate to now (15 ms nominal) | V; Choice for gaps | aligned |
| Preview control law | Offset-free QP | Same PD + unchanged bias observer as Step 1 | User Step 2 | deliberate deviation |
| Duplicate / old / future captures | Not established | Ignore; require increasing sequence and capture time not after current time | Choice | unknown-in-paper |
| Reproduction acceptance | Table IV: feedback 18.3 / 176.8 µm free/contact | Free 15–25 µm; primary contact 150–200 µm | User range; Choice definition of near 20 | deliberate deviation |
| Force saturation | Baseline bound not established | No saturation | Choice | unknown-in-paper |
| Needle DOF / actuator | z slide / motor | z slide / unit-gear motor | VII-A | aligned |
| Needle equivalent mass | 1 g | 0.001 kg | VII, Table III | aligned |
| Needle shape | Generic capsule | Capsule | B-B | aligned |
| Capsule radius / axial segment | Dimensions not established | 0.25 mm / 1 mm | Choice; no fitting | unknown-in-paper |
| Capsule endpoints at q=0 | Not established | z = 0.25 and 1.25 mm | Choice; bottom tip z=0 | unknown-in-paper |
| Needle inertial origin / diagonal inertia | Not established | (0,0,0.25 mm) / (2.5e-11,2.5e-11,2.5e-11) kg·m² | Choice; rotation locked, equivalent translating mass | unknown-in-paper |
| Tissue DOF / actuation | z slide / stiff position servo | Same | VII-A | aligned |
| Tissue servo kp / kv | 8000 N/m / 120 N·s/m | 8000 / 120 | B-B default | aligned |
| Tissue equivalent mass | Not explicitly established | 1 kg | Choice | unknown-in-paper |
| Tissue box dimensions | Not established | 20 × 20 × 10 mm | Choice | unknown-in-paper |
| Tissue inertial origin / inertia | Not established | (0,0,-5 mm) / (1e-4,1e-4,1e-4) kg·m² | Choice; rotation locked | unknown-in-paper |
| Gravity handling | Gravity feedforward | Gravity zero; ideally compensated axis | III-A, VII-C; Choice | deliberate deviation |
| Cardiac amplitude / frequency | 200 µm / 1.2 Hz | Same | VII, Table III | aligned |
| Second harmonic amplitude / frequency | 60 µm / 2.4 Hz | Same | VII, Table III | aligned |
| Respiratory amplitude / frequency | 300 µm / 0.25 Hz | Same | VII, Table III | aligned |
| Harmonic phase | Not established numerically | 0 rad | Choice; Brief formula | unknown-in-paper |
| Fundamental / respiratory phase, DC offset | Not established numerically | 0 rad / 0 rad / 0 m | Choice; Brief formula | unknown-in-paper |
| Tissue initial position / velocity | Not established | d(0) / 0 m/s | Choice | unknown-in-paper |
| Initial needle position / velocity | Not established | 1 mm / 0 m/s | Choice | unknown-in-paper |
| Approach duration | 0–1 s | Same | VII-B | aligned |
| Approach shape | Smooth cosine in PDF v1 p.8 | Cubic smoothstep | Prior Choice; unchanged to isolate contact experiment | deliberate deviation |
| Hover time / reference gap | 1–2 s / 0.5 mm | Same | VII-B | aligned |
| Insertion ramp time / final reference | 2–2.5 s / -0.3 mm gap | Same | VII-B | aligned |
| Ramp interpolation | Ramp; detailed formula not established | Cubic smoothstep | Choice | unknown-in-paper |
| Hold / total duration | 2.5–8 s / 8 s | Same | VII-B | aligned |
| Measurement windows | Free 1–2 s; contact 3–8 s | Same | Table IV | aligned |
| Window endpoint convention | Not established | Half-open; 1000 / 5000 samples | Choice | unknown-in-paper |
| Tip/depth coordinate | Relative tip minus surface | Bottom capsule point minus box top | III; exact geometry offset is Choice | unknown-in-paper |
| Primary effective stiffness | v1 ~16 N/m; v3 discloses ~3 N/m actual | Measured 16.000 N/m | v1 VII-A; Brief; Decision | aligned |
| Diagnostic effective stiffness | v3 ~3 N/m | Measured 3.500 N/m | Decision; approximate diagnostic, not author's model | deliberate deviation |
| Soft contact law | MuJoCo solref/solimp | Same mechanism | VII-A; v3 VIII-A | aligned |
| Primary solref | Not established | (-2669.3333333333335, -179) | Measured calibration | unknown-in-paper |
| Diagnostic solref | Not established | (-583.9166666666667, -179) | Decision; first entry ×3.5/16 only | deliberate deviation |
| solimp, both profiles | Not established | (0.5,0.5,0.001,0.5,2) | Choice | unknown-in-paper |
| Contact dimension / friction | Axial setup; exact settings not established | condim=1; friction=(0,0,0) | Choice | unknown-in-paper |
| Contact margin / gap | Not established | 0 / 0 | Choice | unknown-in-paper |
| Joint damping / armature / limits | Not established | 0 / 0 / unlimited | Choice | unknown-in-paper |
| Integrator / solver | Not established | implicitfast / Newton | Choice | unknown-in-paper |
| Solver iterations / tolerance | Not established | 100 / 1e-12 | Choice | unknown-in-paper |
| Physics step / control tick | 1 ms control cycle; requested 1 ms step | 1 ms / 1 ms; optional integer substeps | VII; Brief; Decision | aligned |
| Surface delay | 15 ms | 15 ms | VII, Table III | aligned |
| Surface sampling rate | 1 kHz nominal; 25 Hz sparse study | 1 kHz default; 25 Hz option | VII; frequency study; Brief | aligned |
| Surface noise / drop probability | Nominal baseline settings not established | 0 m std / 0 probability; configurable | Choice; Brief | unknown-in-paper |
| Noise distribution / missing-frame behavior | Exact baseline implementation not established | Gaussian; independent loss; hold last sample | Choice; Brief | unknown-in-paper |
| Capture/delay order / startup | Not established | Capture then delay; no frame before first arrival | Choice | unknown-in-paper |
| Needle encoder | Exact baseline path not established | Undelayed local position/velocity, 1 kHz | Choice | unknown-in-paper |
| RNG / seed | Benchmark seed not established | NumPy PCG64 / 42 | Choice; user request | unknown-in-paper |
| Controller truth access | Relative-control description; code unavailable | Sensors only; tested import/output separation | Brief; Choice | unknown-in-paper |
| Position / velocity error | Tissue-relative reference error; actual tissue velocity | Same; qpos/qvel, no finite differences | III, VII-D | aligned |
| Contact force readback | mj_contactForce | Sum of normal forces | VII-A | aligned |
| State/force sampling | Exact implementation not established | Pre-tick rows; refreshed post-step mj_forward with held control | Choice | unknown-in-paper |
| Task limits | 20 µm, 2 mm/s | Strict contact RMS <20 µm, peak abs edot <2 mm/s | Brief verdict; paper specs | aligned |
| INVALID / numerical stop | Not established | Incomplete/nonfinite/nonreproducible INVALID; MuJoCo warning stops | Brief; Choice | unknown-in-paper |
| Wall-time scope | Paper includes MPC solver-core timing | Controller + evaluation + plant + sensors; no file I/O | Choice; SIL purpose | deliberate deviation |

Implicit MuJoCo defaults not overridden above are tied to version 3.8.0. They are
not claimed to reproduce unknown author settings. The simplified preview is
documented below; MPC/QP, 3-DOF, HIL and fault campaigns remain outside scope.

## Author code / MJCF search

Search window: **2026-10-12 21:08:57–21:09:39 UTC (42 seconds; under 10 minutes)**.

| Route | Query / inspected item | Result |
| --- | --- | --- |
| Paper | v3 Appendix D-C, pp. 19–20; v1 HTML; arXiv full-text/code links | Script names and requirements file described; no release/repository URL found |
| Web search | Paper ID + GitHub; full title + code; author + Voryx + GitHub | No author release located |
| Exact filenames | `thread_insertion_mujoco.py`, `thread_insertion_realism_study.py` | No matching public code result |
| GitHub CLI repository search | `2608.08860`, `Yongyan Cao`, `Voryx` | First two empty; Voryx hits not identified as this author's release |
| GitHub CLI code search | Both exact filenames above | Empty results |
| arXiv TeX archive | [v3 source](https://arxiv.org/src/2608.08860v3), 1,195,730 bytes, 6 members | No .py, .xml, .mjcf, .ipynb or .mjb members; no HTTP(S) release URLs in inspected TeX/text |

The Python download first encountered a local certificate-chain error; a verified
Windows HTTP client downloaded the archive successfully. It was inspected without
executing any contents. No author was contacted. **No released code/MJCF was found
within this bounded search**; this does not establish that no release exists anywhere.
The search is complete for this checkpoint and does not block the requested CI work.

## Hosted gate and delayed-feedback checkpoint

The user subsequently authorized public repository creation and push. Before changing
controllers, [hosted run 38309462614](https://github.com/Jeffaaay/insertion-vv/actions/runs/38309462614)
at commit `24e4dd42cad761f23eabcdf7012c61be4e4a970b` passed all **43 tests**.
Downloaded trace and repeat-trace files were hashed locally, not merely read from
the job's status. Both were identical to their local Windows 10 counterparts on the
Windows Server 2022 runner (Python 3.12.10, MuJoCo 3.8.0, NumPy 2.2.6):

```text
primary:         66422ccb08f67fe12d37936578bae832bf5b9a3d8fd73b357e82b1861ff118a2
paper_effective: cc7e3e7e556c7719c6ff37ac3f2b1581179f286d8ccf452838acac02e5a8998d
```

That evidence satisfied the original Windows hosted gate. No delayed-feedback code
was implemented before it passed. Both hashes remain strict regression checks only
for their registered Windows fingerprint; Linux has its own measured references.

### Controller choices fixed before the experiment

The controller is finite impedance about the received delayed surface:

`F = kp * (r_ref + d_delayed - z_encoder) + kd * (r_ref_dot + v_filtered - v_encoder)`.

Set kp=10 N/m (100 µm/mN compliance) and kd=0.2 N·s/m, the critical-damping value
`2*sqrt(0.001*10)` for the free needle axis. Select a 5 ms causal first-order velocity
filter. These are our declared engineering choices; the inspected v1 paper states
filtered velocity feedback but does not disclose these gains or filter coefficients.
The gains differ from lab-frame PD: this comparison therefore includes finite
compliance as well as sensing, and cannot attribute all changes solely to delay.

On each new capture, differentiate using capture-time spacing (including dropped
frames), then update with `alpha = dt_sample/(tau + dt_sample)`. Do not repeatedly
differentiate held frames. The first sample initializes position with zero velocity;
before it arrives, use a nominal zero surface. Ignore duplicate/older/future captures.
Between arrivals, hold position and filtered velocity. There is no `v * frame_age`
position advance, physiological waveform, truth access, integral correction, or
contact-force feedback. The independent-process truth-output-toggle test now covers
both controllers and both profiles at 25 Hz with seeded noise and frame loss.

Before running, `sim/reproduction_contract.json` registered 15–25 µm free RMS
(our explicit interpretation of "near 20") and 150–200 µm primary contact RMS.
These are CI reproduction checks, separate from the unchanged task PASS contract.
No gain, filter, plant parameter or acceptance threshold changed after the first run.

### Measured delayed-feedback result, seed 42 (original Windows checkpoint)

| Metric | `primary` | `paper_effective` |
| --- | ---: | ---: |
| Free RMS | 19.310018 µm | 19.310018 µm |
| Contact RMS | 184.430580 µm | 78.092697 µm |
| Contact peak absolute error velocity | 0.125066 mm/s | 0.196022 mm/s |
| Contact peak normal force | 2.132445 mN | 1.012757 mN |
| Whole-run peak force, including insertion transient | 2.175296 mN | 1.610088 mN |
| Task verdict | FAIL (contact RMS >=20 µm) | FAIL (contact RMS >=20 µm) |
| Reproduction checks | PASS: free and primary contact ranges | PASS: free range; contact reported without primary range |

The static spring balance predicts a contact offset `depth*K_env/(kp+K_env)`:
184.615 µm at 16 N/m and 77.778 µm at 3.5 N/m. This explains the scale of the
measured 184.431 / 78.093 µm errors; it is not a replacement for the dynamic metrics.
The softer diagnostic improves contact position at the same gains. Neither result
is an exact reconstruction of the author's undisclosed implementation.

```text
delayed_feedback primary:
13af5a38301ee4c34561f9b4fbe5c64e1d42c877cd9959e3ffec302bacecd71e
delayed_feedback paper_effective:
b4b787c827bfa8e55732d99466dada3af682690cce091077e93d476f1cc2ef9d
```

At that checkpoint the expanded CI entry point ran **65 tests**, calibrated both profiles, and ran
all four controller/profile combinations with deterministic replay. It enforces the
platform-scoped lab-frame hashes and the pre-registered delayed-feedback reproduction bands.
Latest commit-specific hosted status and downloadable metrics/traces are available
on [Actions](https://github.com/Jeffaaay/insertion-vv/actions).

## Two-tier determinism and canonical Linux reporting

The historical Linux diagnostic [run 38315698883](https://github.com/Jeffaaay/insertion-vv/actions/runs/38315698883)
passed all 43 original tests, both calibrations, and both same-seed trace repeats.
Its final cross-OS SHA comparison failed as expected from the observed last-ulp
difference: at trace t=0.351 s, surface_z_m differed by 2.710505431213761e-20 m.
Source/config hashes were equal. [Finding #2](FINDINGS.md#finding-2--cross-platform-last-ulp-divergence)
records complete hashes, capture-versus-arrival timing and interpretation limits.

The user accepted this libm-scale difference and replaced the universal SHA gate:

| Tier | Comparison | Required result |
| --- | --- | --- |
| Intra-platform | Same OS/arch/Python/MuJoCo/NumPy fingerprint, source/config/seed | Exact trace and truth SHA-256 |
| Cross-platform signals | Every trace/truth position, velocity, force sample | Strict absolute differences <1e-12 m, <1e-9 m/s, <1e-12 N |
| Cross-platform task metrics | Free/contact RMS and peaks; whole-run peaks | Strict symmetric relative difference <1e-9 |
| Cross-platform discrete state | Ticks, timestamps, freshness, sequence IDs, counts, verdict and safety state | Exact equality |

Relative difference is `abs(a-b)/max(abs(a),abs(b))`; both zero maps to zero and
one zero to one. Wall-time and UUIDs are excluded. Missing/corrupt/nonfinite or
incompatible evidence is INVALID, never accepted as agreement. The standard-library
`tools/compare_traces.py` validates saved hashes, source/config and run identity before
comparing. The obsolete fixed cross-OS hash workflow is replaced by Linux/Windows
matrix jobs and a third artifact-comparison job. No plant, controller, sine, trace
rounding, reproduction band or task-verdict threshold changes accompany this fix.

Every new run records a platform fingerprint; a historical hash from a different
fingerprint is not applied. Same-platform replay remains mandatory on new/unregistered
platforms. Linux runner results are canonical; Windows results are supporting
cross-platform evidence. Visualization tools replay the Linux run's recorded truth
locally and remain outside CI and test dependencies.

### Verified two-tier checkpoint and canonical delayed feedback

At commit `3303572ccc1f45146fc1b8bc75f687143550bada`,
[hosted run 38316499846](https://github.com/Jeffaaay/insertion-vv/actions/runs/38316499846)
completed with all three jobs green: Ubuntu 24.04, Windows Server 2022, and
cross-platform comparison. Both platform jobs passed **96 tests** with zero
failures/errors/skips, calibrated both profiles, and ran all four controller/profile
cases with seed 42 and exact same-platform replay. Local Windows executed the same
CI entry point on this clean commit; its four trace/truth hashes matched the hosted
Windows files exactly. Downloaded Linux/Windows artifacts were independently
rechecked with the same standard-library comparator.

The largest differences across all four comparisons, including evaluator truth,
were **2.168404344971009e-19 m** position, **1.7780915628762273e-17 m/s** velocity,
and **2.7755575615628914e-17 N** force. The largest physical-metric relative
difference was **1.7754149153478065e-15**. All are strictly within the registered
limits; all corresponding verdicts and discrete fields agree.

The already implemented delayed-feedback controller was verified without changing
gains, estimator, plant or task thresholds. It follows the 15 ms-delayed measured
surface and uses a 5 ms filtered capture-time difference for velocity; it performs
no position prediction. These are the **canonical Linux** results:

| Seed 42 metric | `primary` | `paper_effective` |
| --- | ---: | ---: |
| Free RMS | 19.310017584602836 µm | 19.310017584602836 µm |
| Contact RMS | 184.4305797579661 µm | 78.09269727426855 µm |
| Contact peak absolute error velocity | 0.12506631717776914 mm/s | 0.19602246516378652 mm/s |
| Contact peak normal force | 2.1324453956586886 mN | 1.0127573960638219 mN |
| Task verdict | FAIL: contact RMS >=20 µm | FAIL: contact RMS >=20 µm |
| Reproduction acceptance | PASS: free 15–25 µm, contact 150–200 µm | PASS: free 15–25 µm; primary contact range does not apply |

```text
Linux delayed_feedback primary:
74b760f84911f8c12e1de7eb9aa638c97db56119eb0618e6565b8cce17cdbf60
Linux delayed_feedback paper_effective:
cbd213fe4a0848c196688ef1f5c4f9b17fdc3309fd0c2cd91866df2d6fffe3a7
```

### Optional delayed-feedback visualizations

The Linux job artifact is `phase-a-ubuntu-24.04-3303572ccc1f45146fc1b8bc75f687143550bada`.
Locally it was downloaded to `artifacts/hosted-two-tier-38316499846/linux/`.
For each of `primary` and `paper_effective`, in the separate visualization environment:

```text
python tools/plot_run.py --run artifacts/hosted-two-tier-38316499846/linux/primary/delayed_feedback
python tools/render_video.py --run artifacts/hosted-two-tier-38316499846/linux/primary/delayed_feedback
python tools/plot_run.py --run artifacts/hosted-two-tier-38316499846/linux/paper_effective/delayed_feedback
python tools/render_video.py --run artifacts/hosted-two-tier-38316499846/linux/paper_effective/delayed_feedback
```

Outputs: `artifacts/viz/delayed_feedback_primary_seed42.{png,mp4}` and
`artifacts/viz/delayed_feedback_paper_effective_seed42.{png,mp4}`, plus provenance
JSON sidecars. Both PNGs were visually reviewed. Both encoded videos were decoded
to verify 1280×720, 20 fps, 160 frames, 8 s; frames at 0, 3.2, 5.1 and 7.95 s were
inspected for the HUD, needle/tissue contrast and moving 300 µm depth marker.
Rendering reads recorded states and does not integrate physics. These local
artifacts are ignored by Git and are never CI/test dependencies.

## Optional Step 1: delayed feedback plus acceleration-bias observer

The user requests a single-variable extension and a stop after commit/push/report.
No harmonic estimator or preview is implemented at this checkpoint. Before the
first experiment, register **20–40 µm contact RMS for both profiles**, seed 42, in
`sim/reproduction_contract.json`. Keep task PASS (<20 µm, <2 mm/s, no safety stop),
plant/contact parameters, PD gains, surface delay/filter and reference unchanged.

Use [v1 HTML §V, Eq. (8)](https://arxiv.org/html/2608.08860v1#S5)'s position-only
Luenberger observer with state [p,v,a], nominal mass 1 g, Ts=1 ms and fixed gains
L=[0.6,12,400]. At tick k, predict from corrected state k-1 and previous total
command u[k-1]; then correct all three states with current encoder-position
innovation. Initialize p from the first encoder and v/a at zero. Command
`u = unchanged_delayed_feedback(sensors) - mass * estimated_acceleration_bias`.
This uses the commanded input, not measured contact force. Neither the observer
nor controller receives tissue truth, contact stiffness, waveform or future data.
No observer saturation, contact-mode switch, gain scheduling or tuning is added.

The paper's Table XII 30.3±0.2 µm is a 30-seed **QP** ablation; our seed-42 **PD**
ablation tests the same disturbance-rejection mechanism and the user-requested
magnitude range, not exact table replication. The literal Eq. (8) Euler observer
is preserved although the plant's integrator is implicitfast; discretization
residual can therefore also enter the bias estimate. The actual predict/correct
error transition is `(I-L*C)*A`; no eigenvalue claim is inferred from the paper's
separately written `A-L*C` expression.

### First-run evidence (Windows development environment)

The first run already met the registered range on both profiles. **No tuning was
performed.** These initial records are preserved at `artifacts/offsetfree-first/`;
canonical Linux evidence is recorded separately after hosted verification.

| Seed 42 metric | `primary` | `paper_effective` |
| --- | ---: | ---: |
| Free RMS | 19.300852 µm | 19.300852 µm |
| Contact RMS | 20.630832 µm | 33.618597 µm |
| Contact peak absolute error velocity | 0.361917 mm/s | 0.880340 mm/s |
| Contact peak normal force | 5.592349 mN | 1.979979 mN |
| Whole-run peak normal force | 6.304965 mN | 3.543761 mN |
| Task verdict | FAIL: contact RMS >=20 µm | FAIL: contact RMS >=20 µm |
| Step 1 reproduction acceptance | PASS | PASS |

Primary contact RMS drops from 184.431 to 20.631 µm; diagnostic from 78.093 to
33.619 µm. Free-space RMS remains near 19.3 µm: this step cancels the contact bias,
not the surface-sensing delay. Contact peak force increases from 2.132 to 5.592 mN
and from 1.013 to 1.980 mN as cancellation removes the baseline's under-penetration.
The unchanged task contract has no force threshold; this increase is reported,
not hidden or tuned away. The softer contact is not guaranteed lower error with
the same dynamic observer; no profile-specific gains were used.

Local CI used the workflow's pinned install and `python -m sim.ci` commands:
**130 tests passed**, both calibrations passed, all six seed-42 experiments passed
their reproduction gates and bitwise replay. The four original baseline trace
hashes are unchanged, including both delayed-feedback hashes. New independent
process/truth-output-toggle tests also cover offset-free control with 25 Hz
measurements, seeded noise and frame loss. Unit checks cover hidden-bias
identification with varying input, startup, cancellation sign/previous total
command, invalid frames and bitwise equivalence when bias cancellation is disabled.

### Canonical Linux result and hosted verification

Code commit `ca364c71f19dfccf388f1c2a207a8a9571cdf3ca` passed
[hosted run 38318752405](https://github.com/Jeffaaay/insertion-vv/actions/runs/38318752405):
Ubuntu 24.04 **130/130**, Windows 2022 **130/130**, zero failures/errors/skips,
both contact calibrations, six internally bitwise-repeatable seed-42 cases, and
all **six cross-platform comparisons PASS**. A clean local Windows run used the
same CI commands; all six trace/truth hashes match hosted Windows. Downloaded
artifacts were independently compared and all eight historical baseline traces
(two controllers × two profiles × two OSes) exactly match the prior checkpoint.

| Canonical Linux metric, seed 42 | `primary` | `paper_effective` |
| --- | ---: | ---: |
| Free RMS | 19.30085205372127 µm | 19.30085205372127 µm |
| Contact RMS | 20.63083237812307 µm | 33.618596790679305 µm |
| Contact peak absolute error velocity | 0.3619168846643375 mm/s | 0.8803398605529429 mm/s |
| Contact peak normal force | 5.5923491123020606 mN | 1.979979481464928 mN |
| Task verdict | FAIL: contact RMS >=20 µm | FAIL: contact RMS >=20 µm |
| Step 1 reproduction acceptance | PASS | PASS |

```text
Linux offset-free primary:
0704d13b0dc35e8961678ddc65bcdd355de9651f94eb84283f00ffeae0537af1
Linux offset-free paper_effective:
37929c6efac5a6dea75ef9b408e8f1e182687c2a9ad3ba64c4de46e9aa10e1d5
Windows offset-free primary:
796631e190e63e7c824cadc56078e246d961fe11f289e3653e81282102a7684a
Windows offset-free paper_effective:
2550246cae894b2da973825d39553b0ca31340c6bb76b189d7715ca7d0d5c0c6
```

Across all six comparisons the largest differences are 2.710505431213761e-19 m,
1.7780915628762273e-17 m/s and 2.7755575615628914e-17 N; the largest physical-metric
relative difference is 3.514711358389029e-15. All discrete states and verdicts agree.
Same-platform hashes remain exact; the registered cross-platform tolerances are unchanged.

For interpretation only, the first Windows contact records have mean error
0.851/0.777 µm and standard deviation 20.613/33.610 µm. Thus the RMS is dominated
by time-varying residual, not a large DC offset. The diagnostic has stronger
oscillatory error with these same observer gains. This is an observation from
saved traces, not a fitted frequency model or a claim that preview has been tested.

### Optional Step 1 plots and videos

Source: `phase-a-ubuntu-24.04-ca364c71f19dfccf388f1c2a207a8a9571cdf3ca` from
the hosted run above, downloaded under `artifacts/hosted-offsetfree-38318752405/linux/`.
In the separate visualization environment, for each profile:

```text
python tools/plot_run.py --run artifacts/hosted-offsetfree-38318752405/linux/primary/delayed_feedback_offsetfree
python tools/render_video.py --run artifacts/hosted-offsetfree-38318752405/linux/primary/delayed_feedback_offsetfree
python tools/plot_run.py --run artifacts/hosted-offsetfree-38318752405/linux/paper_effective/delayed_feedback_offsetfree
python tools/render_video.py --run artifacts/hosted-offsetfree-38318752405/linux/paper_effective/delayed_feedback_offsetfree
```

Outputs are `artifacts/viz/delayed_feedback_offsetfree_{primary,paper_effective}_seed42.png`
and `.mp4`, plus provenance sidecars; the combined
`artifacts/viz/delayed_feedback_offsetfree_metrics.json` contains both full Linux
metrics and the six-case cross-platform report. Both PNGs were visually inspected.
Both MP4s were decoded to verify 1280×720, 20 fps, 160 frames / 8 s, and frames
at 0, 3.2, 5.1 and 7.95 s were inspected for clear HUD, contrasting geometry and
the moving 300 µm marker. Rendering replays saved states without physics integration.
No visualization dependency or execution is added to CI/tests.

**Step 1 complete; stop here.** `preview`/harmonic estimation, QP/shear constraints,
Phase B and firmware are not implemented by this checkpoint.

## Step 2: fixed-frequency Kalman preview (preregistered before first run)

User accepted Step 1. Add only the surface estimator/reference preview; retain
the exact `DelayedFeedbackOffsetFree` wrapper, `AccelerationBiasObserver` and
existing baseline code, PD gains, both plants and task verdict. No LQR/MPC/QP,
acceleration feedforward or force constraints are added.

Model `w=[DC,s1,c1,s2,c2,s3,c3]` in metres, with each pair rotating by
`[[cos(w*dt),sin(w*dt)],[-sin(w*dt),cos(w*dt)]]`. Position is DC+sum(s), velocity
is sum(omega*c). Frequencies (1.2/2.4/0.25 Hz) are independent estimator settings;
plant amplitudes, phases, contact parameters and truth are never passed in.
Initialize state to zero and P=(500e-6)^2 I. Select R=(2e-6)^2 m² and isotropic
Qc=(0.2e-6)^2 m²/s; propagate P with exact rotations plus Qc*dt, then use a scalar
measurement correction and Joseph covariance update. These declared choices
precede the experiment; they do not claim to recover unpublished author settings.
The seven-state structure and latency propagation follow
[paper III-B / V](https://arxiv.org/html/2608.08860v1#S3.SS2).

Correct only new valid received frames at their capture timestamps. Reject
premature, old, duplicate or nonfinite measurements. Output propagation advances
from last accepted capture to current time (15 ms nominal; plus age between
sparse/dropped frames) without mutating the filter. Before the first arrival,
use nominal zero position/velocity. Feed the resulting position and analytic
velocity directly into the original PD expression, replacing both delayed
position and filtered-difference velocity. The old controllers are unchanged.

Before running, register **primary contact RMS <=10 µm AND task verdict PASS**;
`paper_effective` is reported with no task-PASS requirement. Both seed 42, same
windows, at most **one tuning pass**. Stop with a plot if primary cannot PASS;
do not relax thresholds or fit more parameters. Tests and CI include both
determinism tiers, all eight cases, and the six historical trace hashes on each
registered platform. Visualizations remain separate from CI dependencies.

### Step 2 first-run history (Windows, no tuning)

Preregistration and implementation were committed as `fb379005d099227233e07ab03db12e7d050cc3d9`
**before** the first preview experiment. Both profiles passed on the first attempt;
**zero tuning passes** were used, with no change to observer, PD or Kalman settings.
Initial evidence is preserved in `artifacts/preview-first/{primary,paper_effective}`.

| First Windows run, seed 42 | `primary` | `paper_effective` |
| --- | ---: | ---: |
| Free RMS | 2.708607306049583 µm | 2.708607306049583 µm |
| Contact RMS | 1.1225636057740722 µm | 7.3502929294236665 µm |
| Contact peak absolute error velocity | 0.07268500727125723 mm/s | 0.4811155397405547 mm/s |
| Contact peak normal force | 4.8533820169486885 mN | 1.3531202577617105 mN |
| Task verdict | PASS | PASS (not required) |

The first full local CI encountered one obsolete scope test: it still listed
`preview` as an invalid controller name. It was changed to a genuinely unknown
name, preserving invalid-name validation. The other 160 tests passed, including
both nominal preview cases. This was a test-scope correction, not a tuning pass.
The reproduction-contract text was also normalized to the repository's LF policy
before CI; no numeric setting or experiment trace was altered.

### Single permitted adjustment: square-root covariance arithmetic

First hosted preview run [38320779592](https://github.com/Jeffaaay/insertion-vv/actions/runs/38320779592)
passed 161 tests on each OS and both nominal task verdicts, but failed the
cross-platform **metric** gate: free RMS relative difference 1.535098882688112e-8
and free peak velocity relative difference 2.986235263498985e-9 exceeded 1e-9.
All position, velocity and force absolute differences passed; the largest preview
position difference was 1.1108106622026437e-13 m. All six historical cases passed.

Diagnostic replay found initial covariance condition numbers about 1.9e7.
Replaying Linux and Windows measurements through the same Windows estimator gave
at most 3.58e-17 m / 1.57e-16 m/s output differences, supporting covariance
arithmetic as the dominant source rather than measurement libm differences.
This is a numerical diagnosis, not proof of a specific BLAS instruction.

Before the next run, consume the **one permitted adjustment** by replacing
Joseph covariance propagation with a QR square-root Kalman implementation of the
same equations. Predict from `[F*S, sqrt(Q)*I]`; triangularize the joint
innovation/state root for scalar correction. Do not reconstruct P during filtering.
An independent covariance-equation test checks prediction and correction.
All frequencies, P0/Q/R values, amplitudes/phase initialization, latency, PD and
acceleration-bias observer remain unchanged. No tolerance, sin implementation,
trace serialization or historical baseline is changed. No further adjustment is
permitted if this version fails acceptance. The first failed CI artifacts remain
available for comparison; no claim of cross-platform bitwise equality is made.

### Final Step 2 nominal result (canonical Linux, seed 42)

Source commit `02ef8e46bf20a46be2b1f76f3b12c4f408cf82ef`, Linux artifact from
[run 38321451277](https://github.com/Jeffaaay/insertion-vv/actions/runs/38321451277).

| Metric | `primary` | `paper_effective` |
| --- | ---: | ---: |
| Free-window RMS, 1–2 s | 2.708607249637172 µm | 2.708607249637172 µm |
| Contact RMS, 3–8 s | 1.1225636065319848 µm | 7.350292930654037 µm |
| Contact peak absolute error velocity | 0.07268500727112626 mm/s | 0.48111553978090826 mm/s |
| Contact peak normal force | 4.853382017220471 mN | 1.3531202578035904 mN |
| Task verdict | PASS | PASS (not required) |
| Step 2 preregistered primary acceptance | PASS | Report only |

Primary contact RMS drops from 20.63083237812307 µm (offset-free only) to
1.1225636065319848 µm. The acceleration-bias observer and PD are exactly unchanged.
No parameter tuning was used; the one allowed adjustment was consumed by the
square-root arithmetic correction. No LQR/MPC, force constraints, Phase B or
frequency adaptation was implemented. Nominal sensing here is 1 kHz and noiseless,
with 15 ms delay; noisy/sparse cases exercise determinism and estimator tests,
not a claim of nominal performance under all faults.

The plot shows remaining insertion transients outside the contact window.
`paper_effective` also has a transient exceeding the instantaneous +/-20 µm
band shortly after 3 s; its window RMS still passes the unchanged task contract.
Force is an output, not a constrained acceptance metric in this simplified PD
experiment. Thus these results do not reproduce the paper's QP/shear constraints.

### Step 2 plots and videos (outside CI)

For each profile, the separate visualization environment ran:

```text
python tools/plot_run.py --run artifacts/hosted-preview-38321451277/linux/primary/preview
python tools/render_video.py --run artifacts/hosted-preview-38321451277/linux/primary/preview
python tools/plot_run.py --run artifacts/hosted-preview-38321451277/linux/paper_effective/preview
python tools/render_video.py --run artifacts/hosted-preview-38321451277/linux/paper_effective/preview
```

Outputs: `artifacts/viz/preview_{primary,paper_effective}_seed42.png` and `.mp4`,
with trace/source provenance in `.plot.json` / `.video.json`. Both plots were
visually inspected. Both videos decode as 1280x720, 20 fps, 160 frames / 8 s;
frames at 0, 3.2, 5.1 and 7.95 s were checked for readable t/e/F overlays,
contrasting colors and the moving 300 µm target marker. Replay never steps physics.
No visualization package is required by CI or tests.

### Step 2 verification and unresolved platform fingerprint limit

Local Windows executed the workflow's pinned install command and full
`python -m sim.ci --output artifacts/preview-sqrt-verified` with the same three
thread/hash environment settings. Lint, formatting, **162 tests**, two stiffness
calibrations, all eight same-runner bitwise repeats and reproduction gates passed.
Hosted [run 38321451277](https://github.com/Jeffaaay/insertion-vv/actions/runs/38321451277)
is green: 162 tests on Windows and Linux, plus all eight cross-platform cases.
Maximum Linux/Windows differences are 3.729655473350135e-17 m,
1.831651150197011e-15 m/s and 2.5299857694949246e-16 N; maximum metric relative
difference is 6.597541894182072e-13. Every verdict and discrete field agrees.

All **12 historical trace hashes and 12 truth hashes** (three prior controllers,
two profiles, two OS artifacts) are unchanged from accepted Step 1 run
38319069038. All six local Windows historical traces/truth also match hosted
Windows. Existing `controllers.py`, plant/MJCF, sensors, reference and verdict
contract have no changes from the accepted Step 1 commit.

| Preview SHA-256 | `primary` | `paper_effective` |
| --- | --- | --- |
| Linux runner | `4b66ee849052f7549e72f768c2a32d288a8c7c57d81c7cf6bb37faeb11fa9029` | `417be91b79640f11290f8219770edbf2616f5cdbcf04473ac0d6a224db3e0ab0` |
| Windows runner | `2b37e3aeca5661d6c829134132e2361ba13717390ac1040dbf0880c43ddd5970` | `9e8323a415b9059e5603931368be729c8b38b5fd19dc1dadd4c855c68d9adb5c` |
| Local Windows | `3231bcd4944bda669441f6c2908e32fda8ef662d28b636dd88a52a96f23a30c4` | `5081e553dab20f37cae0127ad3e7a385f7e0f2c9b90f61865dbe7283fb23c1f2` |

**Unresolved contract issue, not a PASS claim:** the final additional local vs
hosted Windows comparison fails `intra_platform.trace_sha256` and
`intra_platform.truth_sha256` for both preview cases. Both record the same coarse
OS/arch/Python/MuJoCo/NumPy fingerprint, source/config SHA and seed, despite local
Windows 10 versus hosted Windows Server 2022. Each environment is independently
bitwise repeatable, all numeric tolerances pass and verdicts match. The largest
metric relative difference is 3.023326852106384e-13. OS release, CPU and BLAS/LAPACK
implementation/dispatch are not captured by the current fingerprint; platform
linear-algebra differences are suspected, not proved. The square-root filter
fixed tolerance amplification, but does not guarantee bitwise equality between
machines grouped by this fingerprint. Hosted green alone does not settle this.

Evidence: `artifacts/hosted-preview-38321451277/local-vs-hosted-windows.json`;
the unmodified comparison tool returns FAIL as required. The aggregate
`artifacts/viz/preview_metrics.json` records nominal acceptance true, hosted CI
PASS, and `verification_acceptance: false`, with both comparison reports and
per-case local/hosted SHA matches. No gate was relaxed or fingerprint altered.
The single adjustment allowance is exhausted, so controller changes stop here;
the fingerprint/bitwise scope needs a separate decision. No Phase B work started.

## B0: full platform fingerprint closeout

The user authorized continuous work and review exchange toward actual hardware
verification. B0 adopts full platform identity without changing controller or
plant numeric code. Version 2 adds OS release/build, CPU model, NumPy-detected ISA
flags, BLAS/LAPACK build backend and loaded runtime backend/dispatch/thread count.
Data comes from platform/CPU records, NumPy's pinned CPU feature API and
`show_config(mode='dicts')`, plus read-only threadpoolctl 3.6.0. No dispatch or
thread setting is changed by metadata collection. No hostname/install path is stored.

Equal full fingerprints retain exact trace/truth SHA. Different full fingerprints
automatically use the existing position/velocity/force/metric tolerances and exact
verdict checks. Old v1 artifacts are immutable; v1/v2 comparisons are INVALID rather
than inventing provenance. The three old controllers' frozen five-field regression
anchors remain enforced independently of the full-fingerprint comparison tier.

Local full workflow commands pass **170 tests** and eight experiments at `a5c503b`.
Hosted [38322571543](https://github.com/Jeffaaay/insertion-vv/actions/runs/38322571543)
passes 170 tests per OS and all eight Linux/Windows comparisons. Downloaded artifacts
also pass all eight local/hosted Windows comparisons, correctly labelled
`cross-platform-tolerance`. Full evidence: `artifacts/release/phase_a_closeout.json`.

| Field | Local | Hosted Windows |
| --- | --- | --- |
| OS release / version | Windows 10 / 10.0.19045 | Windows 2022Server / 10.0.20348 |
| CPU model | AMD Ryzen 9 8940HX with Radeon Graphics | INTEL(R) XEON(R) PLATINUM 8573C |
| AVX2 / AVX512F / FMA3 | true / true / true | true / true / true |
| BLAS/LAPACK build | scipy-openblas 0.3.29, DYNAMIC_ARCH, Haswell, max threads 24 | same |
| Loaded backend / dispatch / active threads | OpenBLAS 0.3.29 / SkylakeX / 1 | same |
| Python / MuJoCo / NumPy | 3.12.10 / 3.8.0 / 2.2.6 | same |

In this **fresh** Windows pairing all signal and metric deltas are zero, and the
two preview traces have local hashes `3231bcd4...` / `5081e553...`. The prior hosted
Windows hashes `2b37e3ae...` / `9e8323a4...` remain preserved in earlier artifacts.
We do not claim that adding metadata changed arithmetic: local and Linux preview
trace/truth hashes are unchanged, all three older controllers' hashes remain exact
in all three environments, and numeric-source diffs are empty. Hosted runners may
differ between jobs; the old runner's CPU/dispatch was not captured. A specific
historical CPU/BLAS causal assignment is therefore unproven, even though the new
comparison classification and measured acceptance are now correct.

Finding #3 and PHASE_A_SUMMARY include this evidence, four-controller comparisons,
the two transient fault targets, and float32 limitations. Closeout is tagged
`v0.1-phase-a`; Phase B continues only after the requested result/review exchange.
# Phase B B1.1/B1.2 — portable C32, before hardware

Preregistration commit `289eb7c` fixed all thresholds before the first closed-loop
C32 run. The portable C11 implementation uses the same parameters/equations with
binary32 and Householder square-root QR, strict arithmetic, FMA contraction off,
fixed-size arrays and no heap. Phase A source under `sim/` is unchanged.
B1.1 [core CI 38323626662](https://github.com/Jeffaaay/insertion-vv/actions/runs/38323626662)
passes both host builds and Arm GNU 14.2 Cortex-M7 compilation; its accompanying
[Phase A CI 38323626654](https://github.com/Jeffaaay/insertion-vv/actions/runs/38323626654)
passes 170 tests per OS and all comparisons. Sixteen downloaded historical
comparisons pass, including all old-controller SHA anchors.

First B1.2 experiment (local Windows, clang 22.1.8; not canonical Linux):

| Profile | C32 contact RMS (µm) | Peak error velocity (mm/s) | Peak force (mN) | Verdict |
| --- | ---: | ---: | ---: | --- |
| primary | 1.12199245348 | 0.07266675577 | 4.85331661346 | PASS |
| paper_effective | 7.34967569070 | 0.48109550282 | 1.35311318822 | PASS |

Primary original RMS is 1.12256360653 µm; the difference is about 0.0509%, below
the preregistered 5%. Across all 8000 ticks, maximum needle-position difference is
1.71782082763e-8 m (0.017178 µm), below 1e-7 m. Both runs repeat bitwise. Six adapter
tests include full sensor fields, parameter quantization, invalid inputs/reset and
truth-output blindness. Full per-field max/RMS deltas and metrics are preserved in
`artifacts/b1-c32-first/ci_report.json`; no gain/model/noise parameter was tuned.
Hosted C32 values and cross-platform comparison follow in the checkpoint report.

The new controller has a separate CI job/contract, not a relaxed Phase A matrix.
H723's [DP-FPU supports single and double precision](https://www.st.com/en/microcontrollers-microprocessors/stm32h723zg.html);
C32 is an experimental choice. Disabling FMA does not establish equal host/ARM
libm output. Same board binary lockstep/replay requires bitwise equality, while
host/ARM comparison uses the registered Phase B physical tolerances. No board run
or timing result is claimed here.
## B1.2 canonical hosted confirmation

Commit `c11fc27` passes [Phase B CI 38324263962](https://github.com/Jeffaaay/insertion-vv/actions/runs/38324263962)
(six adapter tests per OS, C core checks, ARM compile, both profiles, repeats and
cross-C32 comparison) and [Phase A CI 38324263921](https://github.com/Jeffaaay/insertion-vv/actions/runs/38324263921)
(170 tests per OS, eight cross-platform cases). Local runs of both workflow entry
points pass. All sixteen comparisons to prior Phase A artifacts pass; old three
controller trace/truth hashes remain exact, with no `sim/` source changes.

| Canonical Linux C32, seed 42 | primary | paper_effective |
| --- | ---: | ---: |
| Free RMS (µm) | 2.709114502634 | 2.709114502634 |
| Contact RMS (µm) | 1.121992453479 | 7.349675690702 |
| Contact peak absolute error velocity (mm/s) | 0.072666755770 | 0.481095502815 |
| Contact peak force (mN) | 4.853316613458 | 1.353113188218 |
| Nominal verdict | PASS | PASS |

| Full-run difference from Python, max / RMS | primary | paper_effective |
| --- | ---: | ---: |
| Needle position (m) | 1.71782e-8 / 3.42764e-9 | 1.71782e-8 / 3.70651e-9 |
| Needle velocity (m/s) | 4.73796e-7 / 5.65654e-8 | 4.73796e-7 / 6.02900e-8 |
| Command force (N) | 1.02681e-7 / 4.44156e-8 | 7.50017e-8 / 2.71512e-8 |
| Contact force (N) | 1.02751e-7 / 4.43794e-8 | 7.50576e-8 / 2.70940e-8 |

Primary contact RMS differs by 0.05087935%, passing the 5% budget. Maximum needle
deviation is 0.0171782 µm, passing 0.1 µm. Its slightly smaller RMS is rounding,
not a controller improvement. Linux trace SHA: primary
`d10c9a26602bf94a99789a9c4ef02986aaa823cc909071dede91901c5b3c336f`, diagnostic
`47126e3b76d0ae8209e62bd84af859b6b50713936e3ab8df8aa721680f4c9e34`.
The complete delivered evidence is `artifacts/release/b1_c32_report.json`.

B1.3 registers [the full-input protocol](PROTOCOL.md) with a session ID to reject
previous-run responses, exact tick echoes and CRC. Its 41 B / 29 B request/reply
requires at least 1.5191 ms at 460800 baud. Firmware timing will use separate board
replay; no hardware has been detected or measured at this checkpoint.

## B1.4 Rust orchestration and FFI equivalence

Rust 1.99.0 / edition 2024 adds separate Plant/Controller traits, a bounded Python
plant subprocess, a checked C-library FFI backend and the framed serial/TCP client.
The Python subprocess uses the frozen MuJoCo implementation; no physics, sensor,
controller or evaluator equation is reimplemented in Rust. Binary64 Sensors stay
unrounded through local IPC and are cast once at the C32 boundary. Python returns
canonical record bytes, avoiding differences between JSON float formatters.

Local `cargo fmt`, `clippy -D warnings`, ten Rust tests, release build, twenty
Phase B Python tests, full two-profile `harness.ci`, and the Arm GNU 14.2 Cortex-M7
compile pass. `sim.ci` still passes all 170 Phase A tests and eight experiments.
Both C32 trace/truth pairs equal B1.2 byte-for-byte; all eight local Phase A
trace/truth pairs are unchanged. These local results precede hosted confirmation.

| Local Windows seed 42 | primary | paper_effective |
|---|---:|---:|
| ctypes vs Rust FFI trace/truth | exact / exact | exact / exact |
| Contact RMS (µm) | 1.121992453479 | 7.349675690702 |
| Nominal verdict | PASS | PASS |

Local trace SHA-256: primary
`0a572dbc4985c969883c0a3d4e0eba94ea784b29e891cd0c6faaa77cfa003466`, diagnostic
`b867cb2ac0af7ab4ebde29fecc8df2f293aeaf334143481891f40d3038018e87`.
These are local provenance, not replacements for canonical Linux numbers.
Evidence: `artifacts/b1-rust-local/ci_report.json` and
`artifacts/b1-rust-phase-a/ci_report.json` (plus individual metrics/traces).

Rust compiler/target/executable hash and C numerical-build hash are explicit.
Local Windows Rust uses gnullvm with llvm-mingw; hosted Windows uses MSVC Rust.
Both adapters on each host load the same checksum-verified C library. The C flags,
source and arithmetic remain unchanged. Tests reject CRC/bit corruption, truncated
or oversized packets, incorrect sessions/ticks, nonfinite commands, timeouts,
missing FINISH acknowledgements and malformed metric/sample metadata. Failed
transport yields INVALID with partial evidence. The serial backend is not yet
hardware-validated; protocol loopback unit tests do not measure UART timing.

B1.4 commit `0b89210` is confirmed by green [Phase B CI 38326025235](https://github.com/Jeffaaay/insertion-vv/actions/runs/38326025235)
and [Phase A CI 38326025255](https://github.com/Jeffaaay/insertion-vv/actions/runs/38326025255).
Downloaded Linux/Windows C32 artifacts retain B1.2 trace/truth bytes exactly,
and Rust FFI equals ctypes on both hosts. All sixteen historical Phase A
comparisons pass, with the old three-controller hashes exact. Canonical Linux C32
metrics and both `d10c9a26…` / `47126e3b…` trace hashes are unchanged.

## B1.5 C virtual board through the framed transport

A portable C codec/session handler is shared by the loopback board and the next
STM32 build. The host C process uses the same controller source, compiler, strict
arithmetic flags and libm as the C32 adapter; compiler/flags/source identity and
executable digest are recorded. IEEE binary32 wire values use memcpy/bit encoding,
never decimal formatting. The handler requires HELLO/RESET, exact ticks/session,
complete input fields, and a successful 8000-tick FINISH acknowledgement.

The first complete local run (`artifacts/b1-virtual-local/ci_report.json`) passes:
both profiles and repeats are byte-identical to Rust FFI and ctypes. Contact RMS
remains 1.121992453479 / 7.349675690702 µm, PASS/PASS. Raw transport records retain
actual request/reply bytes and host timestamps. Virtual entry/computation cycles
are explicitly zero; loopback does not stand in for UART or board timing.

C tests consume the same independently generated protocol fixtures as Rust and
reject every single-bit corruption and truncation. Two live-process tests reject
bad CRC and duplicate ticks; Python tests total 22, Rust tests remain 10. Arm GNU
caught a signed-promotion warning in CRC shifting; explicit uint32 shifts resolve
it without changing the CRC or controller arithmetic. The codec and controller
both cross-compile for Cortex-M7 under the existing warnings-as-errors flags.

The final local rerun after that CRC fix is
`artifacts/b1-virtual-verified/ci_report.json`: all ctypes/FFI/TCP trace and truth
bytes still match B1.2 for both profiles. Rust checks and the ARM core/protocol
compile pass; `artifacts/b1-virtual-phase-a/ci_report.json` confirms the separate
170-test Phase A job and eight experiments. Hosted confirmation follows this commit.

B1.5 commit `b4d9992` passes [Phase B CI 38326652708](https://github.com/Jeffaaay/insertion-vv/actions/runs/38326652708)
and [Phase A CI 38326652700](https://github.com/Jeffaaay/insertion-vv/actions/runs/38326652700).
Both hosted backends and all cross-C32 comparisons pass. Sixteen historical Phase A
comparisons pass again; old three-controller trace/truth hashes remain unchanged.

## B1.6 H723 complete image, build-only

The H723 image links the unchanged controller and virtual-board protocol handler
with checksum-pinned ST CMSIS/HAL and Arm CMSIS sources. It configures ST-LINK VCP
(USART3 PD8/PD9, 460800 8N1), circular RX DMA in noncached D2 SRAM, DWT compute
cycles and a TIM6 1 kHz heartbeat. The chosen clock is ST's Nucleo example's
520 MHz, not an assumed 550 MHz. Replay remains unsupported until B2; no timed
control loop or board run is claimed from this compile-only checkpoint.

The first verified local build (`artifacts/b1-firmware-verified/build.json`) has:

| Allocation | Bytes |
|---|---:|
| Flash image incl. initialization and padding | 28960 |
| AXI complete replay inputs | 256000 |
| DTCM telemetry | 104000 |
| Reserved DTCM stack | 16384 |
| DTCM gap before stack | 9728 |
| D2 DMA RX buffer | 512 |

The linker asserts exact replay reservations and prevents stack/data overlap.
Build checks also validate boot vectors, hard-float ABI and real IRQ handlers;
stack-usage reports are retained but are not runtime high-water measurements.
Instruction cache is enabled, data cache disabled, FPSCR=0. Complete provenance,
clock assumptions and the limitation of DWT timestamps while the CPU sleeps are
documented in [the H723 build notes](../firmware/h723/README.md). No board was
detected, flashed or measured in these B1 builds.

Final local workflow commands pass: Phase A 170 tests/eight experiments, Phase B
22 Python and 10 Rust tests with both profiles through ctypes/FFI/TCP, Arm core/
protocol compile, and full H723 link/checks. All local Phase A and C32/FFI/TCP
trace/truth bytes equal their earlier baselines. Final local evidence is under
`artifacts/b1-firmware-{phase-a,host,arm-core,final}`. Full-image CI is now part of
the existing ARM job, separately uploaded as `phase-b-h723-<commit>`; rendering
remains outside every CI dependency.

B1.6 commit `c81c4a4` passes [Phase B CI 38327529395](https://github.com/Jeffaaay/insertion-vv/actions/runs/38327529395)
and [Phase A CI 38327529389](https://github.com/Jeffaaay/insertion-vv/actions/runs/38327529389).
Downloaded C32/FFI/TCP trace and truth bytes remain exact versus B1.2 on both OSes;
16 historical Phase A comparisons pass. The Linux-built and Windows-built firmware
BIN SHA is identical (`e8cabfd41fac22e081b250d8bf10983fd2e341e4d4d35c8ddcfb07e04a988352`);
ELF debug/path metadata differs. Neither image has been flashed. Consolidated
evidence `artifacts/release/b1_ready_report.json` was sent to the authorized Claude
review conversation, which accepted B1.

## B2.1 recorded-input firmware replay, build-only

The B2 plan is registered before any hardware experiment. The review's 512-byte
upload chunks exceeded the protocol limit, so existing 29-byte/tick frames retain
CRC16/sequence/ACK and add complete input CRC32, reserialized from decoded RAM.
The raw 256000-byte C array is not the wire format. START rejects a whole-stream
CRC mismatch; it reinitializes the same frozen controller. No gain or numeric code
changes. The native test runs all 8000 records and requires force bits identical
to direct C execution; it also checks wrong order, corrupt input, invalid ranges,
modular DWT wrap, pending UIF and delayed/coalesced interrupt deadlines.

TIM6 now executes replay. A naked three-instruction entry shim reads CYCCNT before
the compiler/HAL prologue; build tooling verifies its disassembly. The CPU remains
awake while replay runs. DWT and TIM share a clock tree; neither serviced tick
count nor USB host elapsed proves absolute frequency. PG2/D49 instrumentation
supports later independent timing. ISR entry/control/body timings are separate,
with their measurement boundary and excluded epilogue explicitly documented.
Input, command telemetry and extra timing arrays have separate canonical CRC32s.
Stack watermark is conservative unused-prefix evidence; the 4 KiB gate is pending.

The verified local image is 31104 bytes Flash, 256000-byte input + 64000-byte timing
arrays in AXI (7680 spare), 104000-byte telemetry and 16 KiB stack in DTCM (9608-byte
gap), and 512-byte RX DMA buffer in D2. Flash CRC32 will be compared with the host
binary, separately from OpenOCD readback SHA and CI artifact SHA. The old B1 binary
is not a replay image. No board detection, programming, timing PASS or hardware
numerical equivalence is claimed at this build-only checkpoint.

B2.1 commit `dad15b3` passes [Phase B CI 38328737834](https://github.com/Jeffaaay/insertion-vv/actions/runs/38328737834)
and [Phase A CI 38328737818](https://github.com/Jeffaaay/insertion-vv/actions/runs/38328737818).
The downloaded Linux and locally built clean-commit BIN match exactly:
`7bb2abecf63f15c6115c488d3334b4e83f4969dab75861e7768fc0199a31e965`.
All C32/FFI/TCP trace/truth bytes match B1.2 on each OS; 16 historical Phase A
comparisons pass. This image has not been flashed.

## B2.2 hardware host tooling, software-only checkpoint

`tools.board` prepares green main-branch CI artifacts and validates source/image
hashes. Identification checks the observed probe, MCU family/CPUID, UID, 1 MiB
Flash and RDP Level 0. Programming first preserves original Flash locally, guards
the UID again and verifies readback SHA. No protection/option-byte writes or
original-backup uploads. Serial INFO must match the receipt's UID, firmware Git,
controller source and configured clocks; board-computed Flash CRC32 is checked
independently against the BIN. None alone is presented as a timing result.

`harness.hardware` runs both same-board lockstep repetitions, binds actual wire
inputs to trace values and compares against the prepared Linux reference. It adds
the preregistered hardware-only <1% contact-RMS gate without relaxing existing C32
or Phase A contracts. Replay uploads only the recorded canonical 29-byte inputs,
checks the complete RAM CRC, stays quiet during TIM6 execution, then fetches raw
commands and timing. Independent Python analysis checks every command bit, CRC,
count, DWT-wrap interval, timing boundary and scheduled deadline before evaluating
the compute/jitter/stack gates. Partial, corrupt or inconsistent evidence is INVALID;
intact data exceeding a timing threshold is FAIL. Host USB elapsed is not a clock
accuracy test. Absolute frequency remains UNVERIFIED without an external instrument.

The new 24 Python tests use clearly synthetic parser/timing/identity fixtures and
exercise strict gate boundaries, counter wrap, corrupt records, missing FINISH,
wrong/protected devices and preservation of earlier evidence. Rust now has 13
tests, including an actual fragmented TCP transfer of all 8000 replay records and
a runtime-Flash mismatch rejection. That TCP fixture is compiled only for tests,
not exposed by the hardware executable; its timestamps are not board measurements.
`tools.plot_timing` is optional, uses saved verified raw records and adds no CI
dependency. [The runbook](HARDWARE_RUNBOOK.md) supplies the actual-board procedure.

No simulation, controller, firmware or numerical tolerance changed in B2.2.
Software verification and subsequent hosted evidence are recorded with the release
report under `artifacts/release/`; hardware detection/lockstep/replay are still
pending physical connection and must not be inferred from a software CI pass.

Full local workflow verification passes: Phase A 170 tests/eight experiments;
Phase B 46 Python tests, 13 Rust tests, three native C suites, both profiles
through ctypes/FFI/TCP, Arm core compile and full H723 link. Evidence is under
`artifacts/b2-host-{phase-a,local,arm,firmware}`. All 28 local Phase A and C32
backend trace/truth files are byte-identical to B2.1. Serial-port enumeration and
present ST-LINK PnP enumeration are both empty at this checkpoint. Hosted results
will be verified at the resulting commit before any programming step.
