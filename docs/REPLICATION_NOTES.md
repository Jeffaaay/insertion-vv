# Replication notes — Phase A

## Scope and comparison policy

Phase A targets **paper-magnitude baseline with documented deviations**, not bit-exact
paper replication. `lab_frame_pd`, `delayed_feedback`, and the separately authorized
`delayed_feedback_offsetfree` ablation are implemented. The primary plant remains
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
not claimed to reproduce unknown author settings. Preview/MPC, 3-DOF, HIL and fault
campaign parameters are outside this checkpoint's implemented scope.

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
