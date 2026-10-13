# Phase B host harness

The plant, sensor model and verdict evaluator stay in the frozen `sim/` package.
`c32.py` passes only `Sensors` through a checked ctypes ABI to the portable C core.
`run.py` records the same trace/truth/metrics schema using that controller, without
modifying Phase A. `compare.py` applies the separately preregistered C32 budgets;
its exact tier requires both the plant fingerprint and C build to match.

From the repository root, with the Phase A pinned requirements installed:

```sh
cargo +1.99.0 fmt --manifest-path harness/Cargo.toml --check
cargo +1.99.0 clippy --manifest-path harness/Cargo.toml --locked --all-targets -- -D warnings
cargo +1.99.0 test --manifest-path harness/Cargo.toml --locked
cargo +1.99.0 build --manifest-path harness/Cargo.toml --locked --release
python -m harness.ci --output artifacts/phase-b
```

The output directory must be fresh. This runs core and adapter checks, two nominal
contact profiles, deterministic repeats and comparisons against Python preview.
It also runs Rust FFI twice per profile and requires exact trace/truth equality
with ctypes using the same checked C dynamic library. Rust and C build provenance
are recorded separately; wall time includes Python IPC and is not board timing.
CI runs the same command on Linux and Windows; canonical reported values come from
Linux. The original four-controller Phase A workflow and 170 tests remain separate.
The float32 choice is experimental; H723 has a double-precision FPU too. The
Rust `Plant`/`Controller` traits separate simulation/evaluation from control.
`PlantPython` invokes `harness.plant_server`, which uses the unchanged MuJoCo plant
and evaluator. `ControllerInProcessC` and `ControllerSerial` consume only Sensors.
The serial backend is implemented at this checkpoint; C virtual-board and actual
USART validation are subsequent checkpoints, not claimed by the FFI results.

Run a single backend from the repository root (Windows executable adds `.exe`):

```sh
harness/target/release/insertion-harness --backend ffi --python /path/to/python --build artifacts/phase-b/controller-build --output artifacts/raw-ffi --contact-profile primary
```

`--backend serial --port COM5` uses the registered 460800 8N1 protocol;
`--backend tcp --address 127.0.0.1:46081` uses identical frames for the future C
virtual board. Both require the same `--build` source identity and HELLO/RESET/
FINISH acknowledgements. No automatic port selection, retry or flashing occurs.
Partial artifacts and `completion.json` are retained as INVALID on failure.

Rust is pinned to 1.99.0, edition 2024; Cargo.lock pins all transitive packages.
Local Windows uses the gnullvm target with installed llvm-mingw; CI Windows uses
the runner's MSVC Rust target. Both load that host's exact ctypes C library.
Compiler/target/executable digest and the C numerical-build digest are recorded.
