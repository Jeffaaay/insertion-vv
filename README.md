# Current project record — Phase C SIL complete

Start with the **[project journal: text, images and videos](docs/PROJECT_JOURNAL.md)**.
Start visually with the [3D insertion replay](artifacts/c1/videos/insertion-3d.mp4)
([apparatus overview](artifacts/c1/videos/insertion-3d-overview.png)). It uses sealed measured
poses in a 1080p Blender presentation, with an explicitly labeled slow-motion
insertion segment. The apparatus and slender needle are illustrative visual
models; the frozen physics still uses capsule/block soft contact, not puncture. The journal
records the original predictions, the failures, review corrections and the
hardware chapter that remains to be measured. The full multimedia article is
[artifacts/c1/blog.html](artifacts/c1/blog.html); GitHub shows its source. To view
it with embedded video, clone this branch and run:

```text
python -m http.server 8765 --bind 127.0.0.1 --directory artifacts/c1
```

Open `http://127.0.0.1:8765/blog.html`. All media is local; no simulation is run.

Phase C Windows SIL: **3,615 cases attempted twice; 2,730 PASS, 789 FAIL,
96 INVALID**. Of 1,782 Python/C32 pairs, 1,686 valid pairs agree; C32 F6 has
0/96 valid coverage. The 96 incomplete cases remain INVALID. Board measurements
are still pending. Nominal link/timing tools exist; fault-injection HIL tools still
need development. Firmware/tool readiness is not a hardware validation result.

- [One-page results](docs/PHASE_C_SIL_SUMMARY.md) and [sealed predictions](docs/C1_SIL_PREDICTIONS.md)
- [Preregistration](docs/C1_PREREG.md), [findings](docs/FINDINGS.md), [review records](reviews)
- [Figures, videos and matrix](artifacts/c1) and [reproduction/verification](c1/README.md)
- [Hardware runbook](docs/HARDWARE_RUNBOOK.md) for the future HIL chapter

The source and evidence live on `phase-c-sil`. The SIL closeout is pinned at
[8f5dacad](https://github.com/Jeffaaay/insertion-vv/tree/8f5dacad219366b4bfe32caf9a5f8a862633b768).
This journal update changes documentation and presentation, not the sealed matrix.

## Historical baseline README

The complete earlier README follows unchanged. Its references to future Phase C
work describe that earlier checkpoint; use the current links above for Phase C.

<!-- FROZEN_BASELINE_README_BELOW -->
# Insertion verification stack

Headless, deterministic MuJoCo SIL for a 1-axis needle and pulsating tissue.
The project asks when simulation can predict firmware PASS/FAIL; this checkpoint
implements the Phase A plant, `lab_frame_pd`, `delayed_feedback`, its optional
`delayed_feedback_offsetfree` ablation, fixed-frequency `preview`, sensors,
measurements, and CI.

Reported numbers use the **Linux x86_64 runner** (Ubuntu 24.04, Python 3.12.10,
MuJoCo 3.8.0, NumPy 2.2.6) as the canonical platform. Windows is independently
verified and compared with Linux using the two-tier determinism contract below.
The [Phase A closeout](https://github.com/Jeffaaay/insertion-vv/actions/runs/38322571543)
passed **170 tests in local Windows, hosted Windows and Linux**, both calibrations,
eight deterministic experiments per environment, and all eight Linux/Windows and
local/hosted Windows comparisons. Tables below use canonical Linux results; all
six old-controller/profile trace and truth hashes remain unchanged on each OS.
The coarse-fingerprint issue is closed by recording OS release/build, CPU and
BLAS provenance and selecting the comparison tier from the complete fingerprint;
numeric code and tolerances are unchanged. Old failed evidence is preserved.
See the [Phase A summary](docs/PHASE_A_SUMMARY.md) and
[B0 verification record](docs/REPLICATION_NOTES.md#b0-full-platform-fingerprint-closeout).

Phase B software now includes the frozen portable C32 controller, Rust FFI/virtual
transport, H723 lockstep/replay firmware, and host identification, backup, verified
programming and timing analysis. Follow the [hardware runbook](docs/HARDWARE_RUNBOOK.md)
after connecting the NUCLEO-H723ZG through ST-LINK CN1. **No actual board numerical
or timing result is claimed yet.** CI covers software/synthetic protocol evidence;
real UART, TIM6/DWT measurements and stack headroom remain hardware gates. Optional
timing plots remain outside CI and its dependencies.

| Lab-frame PD, seed 42 | `primary` | `paper_effective` |
| --- | ---: | ---: |
| Free-window RMS error, 1–2 s | 270.369 µm | 270.396 µm |
| Contact-window RMS error, 3–8 s | 256.592 µm | 262.055 µm |
| Contact peak absolute error velocity | 2.757 mm/s | 2.846 mm/s |
| Contact peak normal force | 13.283 mN | 4.708 mN |
| Quasi-static contact stiffness | 16.000 N/m | 3.500 N/m |
| Task verdict | **FAIL** | **FAIL** |

The baseline meets the brief's 250–300 µm contact-RMS regression range. This is a
scale reproduction, not an exact reproduction of the paper's force/velocity values.
CI must pass while this deliberately inadequate controller receives a task FAIL.
The 3.5 N/m diagnostic reduces force but **does not meet the expected 2–4 mN range**;
it is preserved without further tuning. This scientific expectation is reported
separately from the verification job's pass/fail status.
See [replication notes](docs/REPLICATION_NOTES.md) for the complete parameter inventory,
versioned paper evidence, prior results and bounded source-code search.

| Delayed feedback, seed 42 | `primary` | `paper_effective` |
| --- | ---: | ---: |
| Free-window RMS error | 19.310 µm | 19.310 µm |
| Contact-window RMS error | 184.431 µm | 78.093 µm |
| Contact peak absolute error velocity | 0.125 mm/s | 0.196 mm/s |
| Contact peak normal force | 2.132 mN | 1.013 mN |
| Task verdict | **FAIL** | **FAIL** |

Delayed feedback tracks the 15 ms-delayed surface without extrapolation, using a
filtered difference of received position measurements for surface velocity.
Its gains (10 N/m, 0.2 N·s/m) and 5 ms filter are declared implementation choices,
selected before the first run; they are not recovered author settings. Primary
meets the registered 15–25 µm free / 150–200 µm contact reproduction ranges.
Both task verdicts still fail the unchanged <20 µm contact-RMS contract.

The optional `delayed_feedback_offsetfree` controller adds only the paper §V
position-encoder acceleration-bias observer, L=[0.6,12,400], and subtracts `m*a`
from the original delayed-feedback command. It uses the previous commanded input;
there is no contact-force readback, truth access, tissue model or surface prediction.
PD gains, reference, sensors and both plants are unchanged. Step 1's contact-RMS
reproduction band is 20–40 µm for both profiles, distinct from task PASS <20 µm.
The paper's 30.3 µm ablation is a 30-seed QP result, not this seed-42 PD experiment.
See the [Step 1 record](docs/REPLICATION_NOTES.md#optional-step-1-delayed-feedback-plus-acceleration-bias-observer).

| Delayed feedback + offset-free, seed 42 | `primary` | `paper_effective` |
| --- | ---: | ---: |
| Free-window RMS error | 19.301 µm | 19.301 µm |
| Contact-window RMS error | 20.631 µm | 33.619 µm |
| Contact peak absolute error velocity | 0.362 mm/s | 0.880 mm/s |
| Contact peak normal force | 5.592 mN | 1.980 mN |
| Step 1 reproduction acceptance (20–40 µm) | **PASS** | **PASS** |
| Task verdict (<20 µm contact RMS) | **FAIL** | **FAIL** |

The first experiment met Step 1 acceptance with the paper's observer gains; no
tuning was performed. Contact mean error is below 1 µm on both profiles, while
time-varying error remains. Removing under-penetration raises contact force from
2.132/1.013 mN to 5.592/1.980 mN; there is no force constraint in this ablation.

The `preview` controller adds a seven-state harmonic Kalman estimator with known
1.2/2.4/0.25 Hz frequencies and unknown amplitudes/phases, corrected only from
received surface frames. It advances the captured state by 15 ms and uses its
position and analytic velocity in the same PD + unchanged acceleration-bias
observer. No force readback, truth access, LQR/MPC or QP is added.

| Preview, seed 42 (Linux) | `primary` | `paper_effective` |
| --- | ---: | ---: |
| Free-window RMS error | 2.709 µm | 2.709 µm |
| Contact-window RMS error | 1.123 µm | 7.350 µm |
| Contact peak absolute error velocity | 0.073 mm/s | 0.481 mm/s |
| Contact peak normal force | 4.853 mN | 1.353 mN |
| Task verdict | **PASS** | **PASS** |

The preregistered primary target was <=10 µm contact RMS **and** task PASS; the
diagnostic was not required to pass. The first implementation met nominal targets.
One subsequent numerical adjustment changed covariance arithmetic to square-root
Kalman QR after the cross-platform metric gate exposed amplified roundoff.
No gains, frequencies, P0/Q/R, plant parameters or tolerances were tuned.
See the [full Step 2 history](docs/REPLICATION_NOTES.md#step-2-fixed-frequency-kalman-preview-preregistered-before-first-run).
This is a nominal known-frequency result, not evidence of robustness to frequency
drift or firmware precision. Startup/insertion transients outside the scored
windows still exceed the plotted instantaneous bands; no force constraint exists.

## Run

Use Python **3.12.10**. From this repository root, in an activated virtual environment:

```powershell
python -m pip install -r requirements-lock.txt
$env:PYTHONHASHSEED = "0"
$env:OMP_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
python -m sim.ci --output artifacts
```

These are the same install and verification commands used by
[GitHub Actions](.github/workflows/phase-a.yml). The same job runs on Ubuntu 24.04
and Windows Server 2022; local Windows verification uses Windows 10. For a POSIX
shell, set the three variables with `export NAME=value` instead of `$env:NAME`.
No display server, viewer, or renderer is opened.
Use a fresh output directory when repeating CI (`--output artifacts/next`) because
run evidence is never overwritten. Artifact upload is a hosted Actions step.

For a single experiment (the runner automatically checks a second identical execution):

```powershell
python -m sim.run --seed 42 --output artifacts/experiment
python -m sim.run --seed 42 --contact-profile paper_effective --output artifacts/diagnostic
python -m sim.run --controller delayed_feedback --seed 42 --output artifacts/delayed
python -m sim.run --controller delayed_feedback --contact-profile paper_effective --seed 42 --output artifacts/delayed-diagnostic
python -m sim.run --controller delayed_feedback_offsetfree --seed 42 --output artifacts/offsetfree
python -m sim.run --controller delayed_feedback_offsetfree --contact-profile paper_effective --seed 42 --output artifacts/offsetfree-diagnostic
python -m sim.run --controller preview --seed 42 --output artifacts/preview
python -m sim.run --controller preview --contact-profile paper_effective --seed 42 --output artifacts/preview-diagnostic
python -m sim.run --seed 42 --sample-hz 25 --noise-std-m 0.000002 --dropout-probability 0.1 --output artifacts/sparse
```

Each experiment writes `metrics.json`, `config.json`, `trace.jsonl`, `repeat_trace.jsonl`,
`trace.sha256`, optional `truth.jsonl`, and `wall_time.csv`. Metrics include run ID,
seed, Git SHA, dirty state, source/config hashes, the contract, and a platform
fingerprint containing OS, normalized architecture, Python, MuJoCo and NumPy versions.
Wall timings and UUIDs are outside the deterministic trace. `--no-truth` disables
only truth-file output; metrics still use evaluation-side truth. Incomplete or
non-reproducible runs are INVALID and return a nonzero exit code.

## Scope and CI gate

Both required Phase A baselines, the optional offset-free ablation and harmonic
Kalman preview are implemented.
Tests cover independent-process
SHA-256 determinism, enabled/disabled truth-file equivalence, sensor timing,
contract boundaries, early termination, stiffness, baseline regression, filtered
velocity, missing/old frames, absence of position extrapolation, hidden-bias
identification, previous-command causality, the zero-bias ablation, learning
unknown harmonic amplitudes/phases, and capture-time preview under sparse/lost frames.
The CI entry point runs four controllers × two contact profiles, producing
`artifacts/{primary,paper_effective}/contact_calibration.json` and
`artifacts/{primary,paper_effective}/{lab_frame_pd,delayed_feedback,delayed_feedback_offsetfree,preview}/metrics.json`
plus traces/timings. Reproduction ranges and all six previous platform-scoped trace hashes
are enforced by [the reproduction contract](sim/reproduction_contract.json).
It reports separate SHA-256 values and the diagnostic expectation in `ci_report.json`.
GitHub Actions runs on every push and PR and uploads all measurement evidence,
including on failures. It requires no repository-specific URLs, credentials, or secrets.

The public remote is [Jeffaaay/insertion-vv](https://github.com/Jeffaaay/insertion-vv).
Before delayed-feedback implementation, [hosted run 38309462614](https://github.com/Jeffaaay/insertion-vv/actions/runs/38309462614)
passed all 43 original tests and reproduced both full local trace hashes on Windows
Server 2022. This released the original controller gate. That checkpoint had 65 tests;
see [Actions](https://github.com/Jeffaaay/insertion-vv/actions) for commit-specific status.
The later Linux verification exposed harmless last-ulp differences; it did not
establish cross-platform bitwise equality. Step 2 adds fixed-frequency preview;
Rust harness, firmware and HIL are now authorized as Phase B work; hardware results
are not yet claimed. Frequency adaptation and Phase C fault campaigns remain future
work. See [Phase B plan and preregistration](docs/PHASE_B_PLAN.md).

## Two-tier determinism

1. **Intra-platform:** identical source/config/seed and platform fingerprint must
   produce bitwise-identical trace and evaluator-truth SHA-256 values. Every run
   replays twice; tests also compare independent processes with truth output on/off.
   The v2 fingerprint includes OS release/build, CPU model and ISA flags,
   BLAS/LAPACK build/runtime/dispatch/thread count, architecture and library versions.
   Historical hashes for the three older controllers keep their original five-field
   scope as additional regression anchors; this is separate from tier selection.
2. **Cross-platform:** different full fingerprints (including different Windows
   machines) select the tolerance tier. Compare all eight Linux/Windows cases.
   Every position difference must be **<1e-12 m**, velocity **<1e-9 m/s**, force
   **<1e-12 N**. Tick times, frame flags/counts and verdicts must match exactly.
   Physical metrics (free/contact RMS and peaks, whole-run peaks) require
   `abs(a-b)/max(abs(a),abs(b)) < 1e-9`; both zero means zero relative error,
   one zero and one nonzero means relative error one. UUIDs, timings, provenance
   strings and cross-platform trace hashes are not numerical metrics.

`tools/compare_traces.py` uses only the Python standard library. It checks artifact
integrity and experiment identity before comparing; missing/corrupt/incomplete runs
are INVALID and cannot pass. Equal fingerprints still require bitwise equality.
The third CI job downloads both platform artifacts and runs:

```text
python tools/compare_traces.py artifacts/linux artifacts/windows --matrix --output artifacts/cross-platform/comparison.json
```

For one case, pass two run directories or their `trace.jsonl` paths (keep companion
metrics/config/repeat/truth files). The old cross-OS SHA gate is replaced by this
job; neither `sin()` nor recorded traces are rounded or patched.
See [findings](docs/FINDINGS.md) for the evidence and Phase B implications.

## Optional visualization

[Plot and video tools](tools/README.md) replay saved Linux artifacts locally, with
a separate visualization environment. They are never executed by CI or imported by
tests, and their optional dependencies are not part of the test environment.
The delayed-feedback checkpoint produced both `.png` and `.mp4` outputs under
`artifacts/viz/delayed_feedback_{primary,paper_effective}_seed42.*`; each video is
1280×720, 20 fps, 160 frames / 8 seconds. See the replication notes for provenance
and commands to regenerate them from the canonical Linux artifacts.
Step 1 also produces
`artifacts/viz/delayed_feedback_offsetfree_{primary,paper_effective}_seed42.{png,mp4}`
and `artifacts/viz/delayed_feedback_offsetfree_metrics.json` with the same isolation
from CI. The optional visuals are local deliverables, not Git-tracked binaries.
Step 2 uses `artifacts/viz/preview_{primary,paper_effective}_seed42.{png,mp4}` and
`artifacts/viz/preview_metrics.json`, also rendered outside CI from saved Linux states.

Directory layout follows [PROJECT_BRIEF.md §8](PROJECT_BRIEF.md).
