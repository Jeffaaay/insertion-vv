# M1 injector acceptance

Ten local tests PASS; final rebuilt Rust binary cross-language test PASS.
Ruff and Rust 1.99 clippy with -D warnings PASS. 104 frozen checks PASS.
- F1 one-tick stale capture boundary and metadata progression.
- F4 25Hz equivalence to frozen sensor path apart from sequence numbering.
- F8 quantization saturation/ties-even; found and fixed Rust negative-zero by
  materializing the registered integer code before converting back to metres.
- F6 skip window; F7 force clipping and full-run 100% identity.
- F5 continuity and frozen prefix.
- Preview and C32 no-fault trace/truth byte-equality to legacy implementations.
- Seeded F2 replay, no-noise same-fault identity, disabled-dropout nominal identity.
- Python/Rust binary equivalence: 8 faults x 2 delay conditions x 8000 frames,
  real MuJoCo surface recordings, plus skip/clip outputs. F5 uses drifted plant samples.
- C32 F6 rejection verified at resumed tick 201 for onset=200/N=1.

Acceptance: shared YAML + random tables, isolated Python/Rust extensions, legacy
hashes preserved, deterministic boundary behavior. Full scientific matrix not run
in M1; validation runs only. CI now exercises these tests on Linux and Windows.
