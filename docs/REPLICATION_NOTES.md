# Replication notes — Phase A

## Scope and comparison policy

Phase A targets **paper-magnitude baseline with documented deviations**, not bit-exact
paper replication. Only `lab_frame_pd` is implemented. The primary plant remains
16 N/m, as specified in PROJECT_BRIEF.md. `paper_effective` is a diagnostic plant,
not a claim to possess the author's MJCF. No controller gains, contact damping,
trajectory, sensor settings or verdict thresholds were tuned after the diagnostic result.

Unless stated otherwise, paper comparisons mean **arXiv:2608.08860v1, HTML Table IV**:
[fixed-version HTML](https://arxiv.org/html/2608.08860v1).
Avoid unversioned PDF URLs when quoting values. Sources were checked on 2026-10-12.
The application-level same-seed trace hash is required to match within one runtime;
there is no claim of bitwise equivalence to the author's implementation.

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
| Controller | Lab-frame PD ignoring surface motion | `lab_frame_pd` only | VII-C | aligned |
| PD kp / kd | Baseline gains not established | 400 N/m / 0.8 N·s/m | Choice, frozen before first run | unknown-in-paper |
| PD law | Fixed lab-frame tracking | Position + velocity error, time-only reference | VII-C; Choice implementation | aligned |
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
