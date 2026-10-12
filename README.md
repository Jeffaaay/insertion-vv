# Insertion verification stack

Headless, deterministic MuJoCo SIL for a 1-axis needle and pulsating tissue.
The project asks when simulation can predict firmware PASS/FAIL; this checkpoint
implements the Phase A plant, `lab_frame_pd`, `delayed_feedback`, sensors,
measurements, and CI.

Reported numbers use the **Linux x86_64 runner** (Ubuntu 24.04, Python 3.12.10,
MuJoCo 3.8.0, NumPy 2.2.6) as the canonical platform. Windows is independently
verified and compared with Linux using the two-tier determinism contract below.
The [two-tier checkpoint](https://github.com/Jeffaaay/insertion-vv/actions/runs/38316499846)
passed **96 tests on each OS**, both calibrations, four deterministic experiments
per OS, and all four cross-platform comparisons. Tables below use that Linux run.

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

Both Phase A baseline controllers are implemented. Tests cover independent-process
SHA-256 determinism, enabled/disabled truth-file equivalence, sensor timing,
contract boundaries, early termination, stiffness, baseline regression, filtered
velocity, missing/old frames, and absence of position extrapolation.
The CI entry point runs two controllers × two contact profiles, producing
`artifacts/{primary,paper_effective}/contact_calibration.json` and
`artifacts/{primary,paper_effective}/{lab_frame_pd,delayed_feedback}/metrics.json`
plus traces/timings. Reproduction ranges and platform-scoped lab-frame reference hashes
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
establish cross-platform bitwise equality. Rust harness,
firmware, preview control, HIL, and Phase C fault campaigns are deferred.

## Two-tier determinism

1. **Intra-platform:** identical source/config/seed and platform fingerprint must
   produce bitwise-identical trace and evaluator-truth SHA-256 values. Every run
   replays twice; tests also compare independent processes with truth output on/off.
   Historical hashes are checked only for their registered platform fingerprint.
2. **Cross-platform:** compare complete Linux/Windows artifacts for all four cases.
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

Directory layout follows [PROJECT_BRIEF.md §8](PROJECT_BRIEF.md).
