# Phase C SIL extension

This package adds registered faults without modifying any of the 104 baseline
tracked files. `faults/README.md` is preserved historical text; implementation now
lives here. `docs/C1_PREREG.md` and its prospective A1 amendment define semantics.

`faults/F1.yaml`–`F8.yaml` use JSON syntax (valid YAML 1.2 subset). The Python and
standalone Rust `FaultInjector` implementations read identical definitions and
precommitted random tables. Rust consumes shared harness types via path dependency;
the legacy crate is unchanged. F5 uses one shared Python MuJoCo plant extension.

The cross-language test feeds identical recorded MuJoCo surface values through
both injectors, then compares packed sample times, sequence, f64 values, fresh
flags, skip decisions and clipped forces byte-for-byte. Both baseline and zero
nominal delay are covered for F1–F8, including actual drifting-plant samples for F5.
Every registered severity and every F2/F3 seed is covered. Other faults use seed 42.
This is injector equivalence; it does not claim a hardware or Rust end-to-end run.

Build the unchanged controller with `python tools/build_controller.py --output
artifacts/c1-build`. Build Rust with `cargo build --manifest-path c1/rust/Cargo.toml
--locked --release --target-dir artifacts/c1-rust`. Set `C1_BUILD` and `C1_RUST`
to the build directory and executable, then `python -m pytest c1/tests -q`.
Missing those environment variables skips optional local ABI checks; hosted CI
sets both and therefore executes the acceptance checks.

Determinism retains the same platform contract. Float32 F6 tick-gap rejection is
an expected validity/coverage boundary, not a FAIL result. M2 retains complete
gzip traces and uses frozen evaluator code. M3 reads sealed evidence only.

## Reproduction

With pinned simulation dependencies and a built frozen controller, set
`OMP_NUM_THREADS=1` and `OPENBLAS_NUM_THREADS=1`, commit the implementation, then
run `python -m c1.matrix --workers 12`. Each logical run is executed twice before
an atomic directory rename. Existing run evidence is hash-checked on resume;
the execution manifest must match the generating commit and numerical platform.
Run-scoped raw metrics remain immutable; derived identity checks live in matrix.json.

`python -m c1.verify_evidence` checks every retained compressed trace/truth hash
and line count against the sealed matrix, without any simulation. With matplotlib
3.10.7, `python -m c1.analyze` writes the registered assessments and five figures
as 300 dpi PNG plus SVG. M3 visualization uses Pillow/imageio/imageio-ffmpeg;
`python -m c1.visualize` reads sealed traces, producing an offline HTML explorer
and eight 8-second MP4 videos. It never imports the simulation or runner modules.
The video font path is Windows Arial; plots record local Windows provenance.

Full lossless evidence remains local under artifacts/c1/runs. Matrix, summaries,
scientific figures, selected curves and videos are the compact published artifacts.
