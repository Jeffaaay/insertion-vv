# Insertion verification stack

Headless, deterministic MuJoCo SIL for a 1-axis needle and pulsating tissue.
The project asks when simulation can predict firmware PASS/FAIL; this checkpoint
implements only the Phase A plant, `lab_frame_pd`, sensors, measurements, and CI.

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
python -m sim.run --seed 42 --sample-hz 25 --noise-std-m 0.000002 --dropout-probability 0.1 --output artifacts/sparse
```

Each experiment writes `metrics.json`, `config.json`, `trace.jsonl`, `repeat_trace.jsonl`,
`trace.sha256`, optional `truth.jsonl`, and `wall_time.csv`. Metrics include run ID,
seed, Git SHA, dirty state, source/config hashes, runtime versions, and the contract.
Wall timings and UUIDs are outside the deterministic trace. `--no-truth` disables
only truth-file output; metrics still use evaluation-side truth. Incomplete or
non-reproducible runs are INVALID and return a nonzero exit code.

## Scope and CI gate

`lab_frame_pd` is the only implemented controller. Tests cover independent-process
SHA-256 determinism, enabled/disabled truth-file equivalence, sensor timing,
contract boundaries, early termination, stiffness, and baseline regression.
The CI entry point runs both contact profiles as a matrix, producing
`artifacts/{primary,paper_effective}/contact_calibration.json` and
`artifacts/{primary,paper_effective}/lab_frame_pd/metrics.json` plus traces/timings.
It reports separate SHA-256 values and the diagnostic expectation in `ci_report.json`.
GitHub Actions runs on every push and PR and uploads all measurement evidence,
including on failures. It requires no repository-specific URLs, credentials, or secrets.

The user will create public `Jeffaaay/insertion-vv` and attach the remote. This local
checkpoint creates no GitHub repository and performs no push. **Hosted CI has not
run.** `delayed_feedback` stays unimplemented until hosted determinism passes;
Phase A overall acceptance therefore remains incomplete. Rust harness, firmware,
preview control, HIL, and Phase C fault campaigns are deferred.

Directory layout follows [PROJECT_BRIEF.md §8](PROJECT_BRIEF.md).
