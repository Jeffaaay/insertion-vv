# Insertion verification stack

Headless, deterministic MuJoCo SIL for a 1-axis needle and pulsating tissue.
The project asks when simulation can predict firmware PASS/FAIL; this checkpoint
implements the Phase A plant, `lab_frame_pd`, `delayed_feedback`, sensors,
measurements, and CI.

| Local baseline, seed 42 | `primary` | `paper_effective` |
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
[GitHub Actions](.github/workflows/phase-a.yml). The job runs on Windows Server 2022;
the local verification uses Windows 10. No display server, viewer, or renderer is opened.
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
seed, Git SHA, dirty state, source/config hashes, runtime versions, and the contract.
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
plus traces/timings. Reproduction ranges and the two original lab-frame trace hashes
are enforced by [the reproduction contract](sim/reproduction_contract.json).
It reports separate SHA-256 values and the diagnostic expectation in `ci_report.json`.
GitHub Actions runs on every push and PR and uploads all measurement evidence,
including on failures. It requires no repository-specific URLs, credentials, or secrets.

The public remote is [Jeffaaay/insertion-vv](https://github.com/Jeffaaay/insertion-vv).
Before delayed-feedback implementation, [hosted run 38309462614](https://github.com/Jeffaaay/insertion-vv/actions/runs/38309462614)
passed all 43 original tests and reproduced both full local trace hashes on Windows
Server 2022. This released the controller gate. The expanded suite has 65 tests;
see [Actions](https://github.com/Jeffaaay/insertion-vv/actions) for commit-specific status.
Evidence establishes the tested local/hosted pair, not every OS or CPU. Rust harness,
firmware, preview control, HIL, and Phase C fault campaigns are deferred.

Directory layout follows [PROJECT_BRIEF.md §8](PROJECT_BRIEF.md).
