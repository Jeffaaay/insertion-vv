# B2 preregistration: firmware replay and actual board verification

Registered before any board is detected, flashed or measured. B1.1–B1.6 passed
local and Linux/Windows hosted checks at `c81c4a4`. Phase A and the portable C32
controller remain frozen. No controller, filter, libm or arithmetic tuning.

## Sequence and gates

1. B2.1 build-only replay: portable replay state machine, checked upload/download,
   H723 TIM6 execution, DWT telemetry and stack watermark; native tests and ARM
   image build. Commit, push and require hosted CI before progressing.
2. B2.2 host tooling: identify probe/MCU; preserve original Flash and read-only
   option-byte evidence; program the newly green B2 binary and read back its
   bytes. Bind SHA-256, build manifest, INFO commit/controller hash/UID/clocks.
   Add recorded-input upload, fetch, verification and reports. Report software
   readiness to the existing Claude review conversation.
3. Once the NUCLEO-H723ZG is physically connected through ST-LINK CN1, perform
   identification and verified programming. Never change protection/option bytes.
   No actuator is attached; MuJoCo remains the plant.
4. Both contact profiles, seed 42: two complete 8000-tick board lockstep runs.
   Same board/binary/host fingerprint must reproduce trace and truth SHA exactly.
   Compare against host C32 using all existing Phase B budgets, plus the stricter
   hardware contact-RMS relative difference <1%. A failure stops hardware
   progression for diagnosis; do not tune. A per-tick UART deadline of 200 ms
   makes a timeout INVALID; initialization retains a separate bounded deadline.
5. Replay each actual lockstep input stream, same board binary, at TIM6 1 kHz.
   Require 8000 force-command bit patterns identical to lockstep. Computation
   p99 <100 us, zero scheduled-deadline misses/overruns, |period jitter| p99 <5 us,
   and at least 4096 untouched bytes of the reserved 16 KiB stack. Incomplete or
   corrupt evidence is INVALID; intact data exceeding a timing gate is FAIL.
6. Report per-profile functional and timing results, raw evidence, compute/jitter
   histograms and measured stack headroom. Only after real gates pass publish a
   Phase B summary/tag. No build or synthetic clock is hardware evidence.

## Transfer and identity

Retain protocol v1's 29-byte sensor payload with tick, CRC16 and ACK per frame;
512-byte chunks would violate its 256-byte payload limit. No silent retries.
8000 records occupy 232000 canonical wire bytes and 256000 decoded RAM bytes.
CRC32/ISO-HDLC (reflected polynomial 0xEDB88320, init/xorout 0xFFFFFFFF,
`123456789` -> 0xCBF43926) covers the canonical serialized records, never C padding.
Firmware recomputes the input CRC from RAM before START, which carries the host
CRC. Telemetry CRC covers 8000 complete 17-byte COMMAND payloads. Fetches use the
already registered chunks of at most ten records, each with the envelope CRC16.

The flashable B1 image `e8cabfd4...` has no replay; use the new B2 CI image.
Do not embed a circular SHA of the entire image into itself. OpenOCD readback SHA
binds the manifest's binary; INFO identifies commit/core/board, and a runtime CRC32
of the linked Flash image supplies an additional independent content check.
The original Flash backup remains local and is not uploaded to Claude or GitHub.

## Timing semantics and limitations

Configured core 520 MHz, TIM6 kernel 260 MHz, PSC=259, ARR=999. A naked entry shim
reads CYCCNT before the C/HAL prologue (after unavoidable hardware exception entry
and address-load instructions). `compute_cycles` brackets only unchanged
`ctrl_step`; entry cycles bracket interrupt scheduling, not computation.
Period jitter[k] = unsigned32(entry[k]-entry[k-1]) - 520000 cycles. Publish signed
and absolute jitter p50/p95/p99/min/max, and compute p50/p95/p99/max, divided by the
reported clock. CPU never sleeps while replay is armed/running; I-cache on,
D-cache off, no UART handling or output in the timed loop.

TIM6 is restarted from CNT=0 after the START acknowledgement has transmitted.
DWT readings immediately before and after setting CEN bound the start epoch.
Tick 0 is released one period later. An exit with a newly pending UIF, computation
>= one period, or completion at/after its scheduled next-release deadline marks
a miss. Scheduled deadlines use the earlier start bound conservatively; report
the start-window width. This also catches delayed/coalesced interrupts that a
serviced ISR count alone cannot reveal. Use modulo subtraction and accumulated
adjacent cycle differences; never treat the serviced TIM6 count as an independent
oscillator. Runtime must retain all 8000 records or be INVALID.

Boot paints only unused stack below current MSP, with a safety gap; the untouched
prefix gives conservative remaining headroom, not a claim about every possible
future call path. If <4 KiB remains, stop and redesign placement. The remaining
AXI space cannot accommodate all 104 KiB telemetry without another layout change.
The B2 timing breakdown consumes an additional 64 KiB (64000 bytes), leaving
7680 bytes of AXI; this allocation is checked by the linker/build.

The review additionally requested an external instrumentation pin. PG2 (ZIO D49,
CN8 pin 14, [UM2407 Table 19](https://www.st.com/resource/en/user_manual/um2407-stm32h7-nucleo144-board-stmicroelectronics.pdf))
is a 3.3 V output, high during the measured ISR body and low afterward. It is an
instrumentation signal, never an actuator command. Report entry-to-control delay,
control duration and measured ISR body separately. The last excludes its own
sample/store, GPIO clear and exception epilogue; no software timestamp observes
its own return. Absolute tick-rate accuracy remains UNVERIFIED until measured
with independent calibrated equipment.

Host START-ACK-to-completion includes USB/OS/poll latency: report it with that
uncertainty, never enforce 8 s +/-1 ms or infer MCO accuracy from it. DWT and TIM
share the clock tree; absolute frequency verification needs independent calibrated
equipment. Board-vs-host numerical differences are measurements; libm causality
remains a hypothesis unless isolated. These limitations do not relax any gate.
