# Portable controller

`controller.c` is the binary32 port of Phase A preview: unchanged gains/model,
PD + position-only acceleration-bias observer + capture-time square-root Kalman
filter and delay preview. It uses C11, fixed arrays, no allocation, no simulator
or evaluator capabilities. Integer tick/capture/sequence fields preserve freshness
semantics; SI float inputs are quantized once at the controller boundary.

Compile with `python tools/build_controller.py --output artifacts/controller-build`.
Use `--arm-cc <arm-none-eabi-gcc>` to cross-compile a Cortex-M7 object as well.
The host compiler comes from `--cc`, `CC`, or `cc`/`gcc`/`clang` on PATH.
Build metadata records compiler versions, flags, source and binary SHA-256.

`-O2 -ffp-contract=off -fno-fast-math` applies to host and ARM. ARM adds
`-mcpu=cortex-m7 -mthumb -mfpu=fpv5-d16 -mfloat-abi=hard`.
The FPU flag is the H723 target ABI, not proof of hardware timing or libm equality.
Only math library calls use floats (`sinf/cosf/sqrtf/hypotf/copysignf`); QR never
forms the covariance matrix. Status errors invalidate the run; reset before reuse
after a numerical failure. The caller must serialize access to each state.

See [Phase B preregistration](../../docs/PHASE_B_PLAN.md) before any experiment.
