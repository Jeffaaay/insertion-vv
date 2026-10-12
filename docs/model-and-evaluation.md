# Phase A model and evaluation decisions

## Scope

The user's instruction limits this checkpoint to the Phase A plant and lab-frame PD,
with no other controller before a hosted CI determinism pass. The brief is the design
input; its later phases and preview controller are not authorization for implementation.
The user owns creation of the public GitHub repository and adding its remote.

## Physical model

All calculations use metres, seconds, kilograms and newtons. The MJCF has two z-slide
joints: a motor-driven 0.001 kg needle and a 1 kg tissue body driven by a position
servo (8,000 N/m, 120 N·s/m), aligned to paper v1 Appendix B-B. Tissue mass remains
our explicit modeling choice. Gravity is zero, representing ideal
gravity compensation along the axis; no gravity compensation accesses ground truth.
The timestep and control tick are both 1 ms, with implicitfast integration and a Newton
solver (100 iterations, tolerance 1e-12). The backend also supports integer substeps.

The needle tip is a capsule with a 0.25 mm radius and a 1 mm axial segment; the
paper states the capsule shape but does not establish these dimensions. Its joint
coordinate is the bottom tip, so its signed gap is needle_z minus tissue_z.
The tissue box has a 20 × 20 mm
top and is 10 mm thick. Soft overlap represents penetration; there is no cutting or
deformable-tissue model. Contact has one frictionless normal constraint.

The servo target is the sum of 200 µm at 1.2 Hz, 60 µm at 2.4 Hz, and 300 µm at
0.25 Hz. The unspecified harmonic phase is fixed to **0 radians**, not randomized or
fitted. Evaluation uses actual tissue qpos/qvel, not the waveform or its derivative.
The finite servo lag is therefore included in every metric. The servo test checks
each harmonic against the independent mass-spring-damper frequency response; the
old <5 µm tracking bound for the much stiffer servo no longer applies.

MuJoCo's direct `solref` parameters are acceleration-space quantities; assigning
`-16` would not establish a 16 N/m physical spring. See the official
[MuJoCo 3.8 solver documentation](https://mujoco.readthedocs.io/en/3.8.0/modeling.html#solver-parameters).
Calibration holds the tissue target at zero and applies eight constant needle motor
loads spanning a 50–900 µm depth range, allowing five seconds to settle for each.
Loads scale with the selected target stiffness so both profiles cover the same
depths; positions remain unconstrained. It fits measured normal
force against actual penetration, checking residual velocity and force balance.
The initial `solref=-8008 -179` measured 48 N/m. Changing only the stiffness term to
`solref=-2669.3333333333335 -179` gives 16.000 N/m, now verified at 50–900 µm, with
`solimp=0.5 0.5 0.001 0.5 2`. The CI calibration file records every point and fit.
The measured stiffness tolerance, fixed before acceptance, is ±5%.
The `paper_effective` diagnostic scales only the first `solref` entry by 3.5/16,
giving `-583.9166666666667 -179` and measured stiffness 3.500 N/m. Primary physics
is unchanged by adding this selectable profile. It is explicitly not the author's MJCF.

## Task and controller

Positive z is away from tissue. A cubic smoothstep approaches from 1 mm to 0.5 mm
over 0–1 s; 1–2 s holds 0.5 mm; a cubic ramp moves to -0.3 mm over 2–2.5 s; the
setpoint holds until 8 s. The initial 1 mm height and cubic profiles are documented
choices where the brief specifies only smooth approach/ramp. PDF v1 explicitly
describes a cosine approach; our cubic approach is recorded as a deliberate deviation
and was held fixed during the contact-only diagnostic.

The lab-frame PD uses `F = 400*(z_ref - z_encoder) + 0.8*(v_ref - v_encoder)` in SI
units. The gains were selected before the first trajectory run; they are not tuned
to the task verdict. Its setpoint never includes surface motion. No force feedforward,
prediction, integral term, saturation model, or second task controller is implemented.
The high-stiffness tissue servo is part of the prescribed plant.

The surface sensor has a 15 ms transport delay, 1 kHz or 25 Hz capture, configurable
Gaussian position noise, and configurable independent frame loss. Before the first
delayed arrival it reports no surface frame. Afterwards it holds the last arrival,
with original sample timestamp, sequence number, and freshness flag. Capture precedes
delay; loss occurs at capture. Randomness uses explicitly seeded NumPy PCG64.
The local needle encoder supplies synchronous position/velocity at 1 kHz. The delay,
noise and dropout options apply to the surface channel, consistent with the paper's
surface-sensing latency; this distinction is explicit rather than implicit truth access.
Sensor loss is an intentional scenario, not a missing evaluation record.

The controller has only immutable scalar Sensors/Command values and time-only task
parameters. It has no plant handle, Truth import, evaluation file path, or tissue
waveform parameters. Static import checks and an independent-process comparison with
truth output toggled enforce that boundary. This is a software architecture boundary,
not a security sandbox against malicious Python code.

## Measurements and verdict

Trace rows are sampled at the start of each tick, 0 through 7.999 s; the last physics
step reaches 8 s. All quantities in a truth row refer to the same pre-step state.
After each step, `mj_forward` refreshes contact forces at the new qpos/qvel with the
held control. Free and contact windows are half-open [1,2) and [3,8), giving exactly
1,000 and 5,000 samples. The label "free" identifies the prescribed time window;
the fixed lab setpoint can still brush the moving surface. Its measured free-window
force is retained rather than suppressed.

`e = reference_gap - (needle_z - tissue_z)` and
`edot = reference_velocity - (needle_v - tissue_v)`. RMS is computed from all e samples
in the window; velocity peaks use actual plant velocities, never finite differences.
Force is the summed normal `mj_contactForce` readback. Per-window and whole-run peaks
are reported so transition transients remain visible.

The registered [contract](../sim/verdict_contract.json) is loaded before simulation.
PASS requires contact RMS <20 µm, contact peak |edot| <2 mm/s, and no safety stop.
Equality fails. Numerical warnings trigger a safety stop; incomplete, missing,
nonfinite, or non-reproducible evidence yields INVALID before task PASS/FAIL.
There is no invented biological force safety threshold. A task FAIL does not make
the verification job fail; the regression expects this poor controller to fail.

Each run performs a fresh same-seed repeat, checks both control and evaluation traces,
and reports both SHA-256 values. CI also checks independent processes with seeded
noise/loss at 25 Hz and toggles optional truth-file output. The trace contains sensors
and commands; evaluation truth lives in a separate file. Neither includes UUIDs,
timestamps from the host, paths, Git metadata, or wall times. Bitwise equality is
required within the same runtime environment, not across operating systems/CPUs.

Each tick's wall time includes controller computation, evaluation readback, physics
stepping, and sensor update. It excludes JSON serialization/disk I/O; it is SIL host
timing, not controller-only firmware timing or a real-time deadline guarantee.

## Interpretation

The aligned primary's 256.592 µm contact RMS meets the brief's magnitude gate (250–300 µm).
Force and velocity are not exact reproductions of
[the paper's Table IV](https://arxiv.org/html/2608.08860v1). Unspecified phase, gains,
contact damping and geometry are declared in the [replication notes](REPLICATION_NOTES.md),
including the paper's version-dependent contact-stiffness statements. No claim of
full numerical replication or real-tissue validity is made. No thresholds were changed
to make the baseline PASS. The diagnostic's peak force is 4.708 mN, outside the
2–4 mN expectation; no tuning follows that result. Delayed-feedback acceptance and
hosted CI remain pending.
