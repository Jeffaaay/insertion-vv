Reserved for the later Rust harness described in PROJECT_BRIEF.md §4/§8.
Phase A currently uses the Python backend in `sim/plant.py` and runner in `sim/run.py`.
The backend exposes reset(seed), step(Command, dt_us) -> Sensors, and truth() for evaluation.
No Rust backend, serial transport, or HIL code is implemented in this checkpoint.
