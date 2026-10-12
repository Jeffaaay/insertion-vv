# Phase B host harness

The plant, sensor model and verdict evaluator stay in the frozen `sim/` package.
`c32.py` passes only `Sensors` through a checked ctypes ABI to the portable C core.
`run.py` records the same trace/truth/metrics schema using that controller, without
modifying Phase A. `compare.py` applies the separately preregistered C32 budgets;
its exact tier requires both the plant fingerprint and C build to match.

From the repository root, with the Phase A pinned requirements installed:

```sh
python -m harness.ci --output artifacts/phase-b
```

The output directory must be fresh. This runs core and adapter checks, two nominal
contact profiles, deterministic repeats and comparisons against Python preview.
CI runs the same command on Linux and Windows; canonical reported values come from
Linux. The original four-controller Phase A workflow and 170 tests remain separate.
The float32 choice is experimental; H723 has a double-precision FPU too. The
Rust orchestration and physical serial backend are subsequent B1 checkpoints.
