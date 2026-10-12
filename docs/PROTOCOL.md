# Controller wire protocol v1

Registered at B1.3 before implementing the Rust/firmware codecs. MuJoCo stays on
the PC; this protocol carries controller measurements and commands, never truth,
tissue configuration or contact-force feedback. Transport: USART3 through ST-LINK
VCP, 460800 baud, 8 data bits, no parity, 1 stop bit, no flow control. A loopback TCP
virtual board uses the same codec for software tests; it is not UART evidence.

## Envelope and byte order

All integers are unsigned little-endian unless stated. Floats are finite IEEE 754
binary32 in SI units, with one round-to-binary32 conversion at the controller
boundary. Encode fields individually; never transmit padded C/Rust structures.

| Byte offset | Size | Field |
| ---: | ---: | --- |
| 0 | 2 | Sync bytes `A5 5A` |
| 2 | 1 | Version, exactly 1 |
| 3 | 1 | Message type |
| 4 | 2 | Payload byte length, maximum 256 |
| 6 | 4 | Session ID |
| 10 | length | Payload |
| 10 + length | 2 | CRC16, little-endian |

Total overhead is 12 bytes. CRC-16/CCITT-FALSE: polynomial 0x1021, initial 0xFFFF,
no input/output reflection, final XOR 0; covers bytes 2 through the last payload
byte (version/type/length/session/payload), excluding sync and CRC. Check vector
ASCII `123456789` gives 0x29B1. Golden independent `binascii.crc_hqx` vectors are in
`harness/tests/data/protocol_v1.json`; implementations must match them byte for byte.

Unknown version/type, impossible length, CRC error, nonfinite required float,
wrong session or tick, EOF, or timeout makes the current run INVALID. No retry may
silently skip a measurement or advance the plant. At a new connection, discard
old buffered traffic before HELLO/RESET; after RESET, any unexpected bytes/frames
invalidate the run. Bounded buffering is required (at most the largest frame plus
explicit transport buffering). A new session/reset starts a new run and artifact.
Default per-request deadline is 2 s, measured from the start of sending; a handshake
uses 5 s. Reads may be fragmented; the deadline is total, not refreshed per byte.

## Messages

| Type | Name | Direction | Payload bytes |
| --- | --- | --- | ---: |
| 0x01 | HELLO | host → controller | 0 |
| 0x81 | INFO | controller → host | 140 |
| 0x02 | RESET | host → controller | 5 |
| 0x82 | ACK | controller → host | 2 |
| 0x03 | SENSORS | host → controller | 29 |
| 0x83 | COMMAND | controller → host | 17 |
| 0x04 | FINISH | host → controller | 4 |
| 0x05 | REPLAY_LOAD | host → controller | 29 |
| 0x85 | REPLAY_LOAD_ACK | controller → host | 5 |
| 0x06 | REPLAY_START | host → controller | 0 |
| 0x07 | REPLAY_STATUS | host → controller | 0 |
| 0x87 | REPLAY_STATE | controller → host | 9 |
| 0x08 | REPLAY_FETCH | host → controller | 6 |
| 0x88 | REPLAY_DATA | controller → host | 6 + 17 × count |

Replay types are reserved for B2. B1 firmware advertises only LOCKSTEP capability
and returns an unsupported status for replay commands. An unsupported/stub mode
can never satisfy a hardware timing gate.

### Identification and reset

HELLO/INFO use session 0. INFO payload in order:

| Field | Encoding | Meaning |
| --- | --- | --- |
| device_kind | u8 | 0 = virtual, 1 = NUCLEO-H723ZG |
| controller_abi | u8 | exactly 1 |
| capabilities | u16 | bit 0 LOCKSTEP; bit 1 REPLAY |
| core_clock_hz | u32 | DWT clock; zero on virtual board |
| timer_clock_hz | u32 | actual TIM kernel clock; zero on virtual board |
| max_ticks | u32 | 8000 |
| firmware_git | 40 ASCII bytes | full lowercase git commit hex |
| controller_sha256 | 64 ASCII bytes | SHA256(controller.c bytes + NUL + controller.h bytes) |
| device_uid | 12 raw bytes | STM32 UID; all zero on virtual board |
| mcu_idcode | u32 | raw DBGMCU IDCODE; zero on virtual board |
| arm_cpuid | u32 | raw SCB CPUID; zero on virtual board |

Firmware build manifest additionally records ELF SHA, compiler/version/flags,
clock tree, FPU configuration and source/config digests. Host records that manifest
and INFO; host/virtual results must remain labeled as such. H723 has a DP-FPU;
binary32 is this experiment's selected precision, not a device limitation.
Rust version/target and a canonical hash of the C numerical compile flags/compiler
and source digests belong in every harness run's provenance. The ctypes library
and virtual executable must match those numerical-build fields (including the
same libm); their different link options and binary digests are recorded separately.

RESET uses a newly generated nonzero u32 session ID in the envelope. Never reuse
that ID within a host process. Payload: `mode u8`, `expected_ticks u32` (8000).
Mode 0 = LOCKSTEP; mode 1 = load for REPLAY. Successful RESET clears controller
state, tick counters and replay state, atomically adopts the session, and returns
ACK with the same session. ACK payload: `request_type u8`, `status u8`.
A stale previous-session reply cannot be mistaken for the new run's tick zero.

### Complete sensor capability

SENSORS/REPLAY_LOAD payload offsets (29 bytes):

| Offset | Encoding | Field / unit |
| ---: | --- | --- |
| 0 | u32 | tick, starting at 0 |
| 4 | u32 | current logical time, µs |
| 8 | u32 | surface capture time, µs |
| 12 | u32 | surface measurement sequence |
| 16 | f32 | needle position, m |
| 20 | f32 | needle velocity, m/s |
| 24 | f32 | delayed surface position, m |
| 28 | u8 | flags |

Flag bit 0 = surface valid; bit 1 = fresh. Legal values 0, 1, 3; reject other bits
or fresh without valid. With valid=0, capture/sequence/surface fields are exactly
zero placeholders and no measurement is fabricated. Held measurements have valid=1,
fresh=0 and retain their original capture/sequence. The current run uses 1 ms
logical ticks (`time_us = tick * 1000`); surface delay is 15 ms. Lost/held samples
are handled by the existing controller freshness rules, not by renumbering them.

Needle velocity and capture time/sequence are required by the existing controller.
Omitting them would change PD or estimator semantics. The original unquantized
sensor values stay in the host trace; the wire bytes separately record the exact
binary32 input passed to C, allowing later replay of the actual controller inputs.

### Command and completion

COMMAND payload offsets (17 bytes): `tick u32` at 0, `force_n f32` at 4,
`entry_cycles u32` at 8, `compute_cycles u32` at 12, `status u8` at 16.
The session and tick must echo the one outstanding SENSORS request. No pipelining
in functional lockstep. The host advances MuJoCo exactly once only after a valid
reply. Virtual timing fields are zero, with device_kind=0. Real entry_cycles is the
raw DWT counter; compute_cycles is unsigned end-minus-start modulo 2^32 and excludes
UART waiting/transmit. Lockstep elapsed wall time is logged separately on the PC.

Status low seven bits: 0 success, 1 malformed input, 2 sequence/session mismatch,
3 unsupported, 4 controller numerical failure, 5 buffer overflow, 6 incomplete.
Any low-bit error invalidates the run. Bit 7 is reserved for a replay deadline miss
with otherwise valid output: this fails the timing gate, not transport validity.
B1 lockstep never claims timing PASS based on these fields.
The review's provisional `board_ts_us` is deliberately named `entry_cycles` here:
raw cycles plus the recorded clock preserve sub-microsecond resolution and expose
wrap handling. Virtual and hardware payload layouts are identical, with virtual
entry/compute values zero.

After tick 7999, FINISH carries `completed_ticks u32` = 8000. Controller returns
ACK only if its completed count matches. Missing FINISH acknowledgement invalidates
the protocol run even if the host already logged 8000 command rows. The host stores
raw TX/RX, session, tick, CRC/error counts and monotonic send/receive times; wall
time/session/DWT metadata are excluded from numerical trace SHA.

### Replay reservation (B2)

RESET(mode=1) → 8000 REPLAY_LOAD frames in tick order → REPLAY_START. Each load is
acknowledged with `tick u32, status u8`. Loading never steps the controller. START
resets controller state, acknowledges readiness, then drives the stored logical
inputs using the hardware 1 kHz TIM interrupt. No UART transport is in that loop.

REPLAY_STATE: `state u8` (0 loading, 1 running, 2 complete, 3 error),
`completed_ticks u32`, `deadline_misses u32`. FETCH is allowed only once complete:
`first_index u32, count u16` (1–10, within the recorded count). DATA repeats those
six bytes then count COMMAND payloads with their original ticks. Record every
entry counter, compute duration and deadline flag. Unwrap adjacent DWT differences
modulo 2^32 using the measured core clock; at 550 MHz the counter wraps within an
8 s replay, so raw subtraction without wrap handling is invalid.

Publish computation p50/p95/p99/max and interrupt-period jitter. Pre-registered
gate: p99 <100 µs, zero 1 ms deadline misses across 8000 ticks, and command bits
identical to the same binary's lockstep run for the same stored inputs. Scheduling
lateness and compute-overrun definitions will be tied to the actual TIM/DWT startup
in B2 before its first hardware experiment. No assumed USB latency or estimated
computation cost is substituted for measurement.

The complete input structure is 32 aligned bytes/tick (256000 bytes for 8000),
not the earlier abbreviated 96 KB estimate. Telemetry can omit redundant tick
storage and use separate force/entry/compute/status arrays (104000 bytes). The
linker must place these in suitable SRAM banks, leave stack/firmware headroom and
publish section sizes before flashing; nominal total RAM alone is insufficient.

## UART budget

8N1 uses 10 serial bits/byte: 460800 / 10 = 46080 B/s in each direction.
SENSORS = 29 + 12 = 41 B → 0.889757 ms; COMMAND = 17 + 12 = 29 B → 0.629340 ms.
The dependent request/reply wire lower bound is 70 × 10 / 460800 = **1.519097 ms**.
UART may be full duplex, but this lockstep command depends on the completed input
frame, so request/reply times add. 8000 ticks require at least 12.1528 s of wire
time, before USB/driver/OS/compute overhead. Functional lockstep cannot establish
a real-time 1 kHz closed loop. Board replay supplies separate timing evidence.

| Budget component | Current value | Evidence |
| --- | ---: | --- |
| Request + reply serialization | 1.519097 ms minimum | exact frame lengths / configured baud |
| USB ST-LINK VCP / driver latency | unmeasured | measure after connection; do not assume 1 ms |
| Controller computation | unmeasured on board | DWT in the actual binary |
| Host scheduling / MuJoCo | host-run wall-time artifacts | separate from board timing |

## Host plant IPC

Rust owns orchestration, not physics. Python MuJoCo is a child process with bounded
length-prefixed binary messages over stdin/stdout; stderr is diagnostics only.
Every packet starts with a little-endian u32 byte count (maximum 1 MiB), then a
u8 operation. RESET/OBSERVE/STEP/FINISH keep one request outstanding, validate ticks,
and abort on timeout/EOF/exception. This local IPC uses binary64 sensor values;
only Controller C32/serial boundaries quantize them to binary32.

Python evaluates truth and uses the same canonical JSON encoder as Phase A. It
returns canonical trace/truth byte records to the Rust logger, so decimal formatting
differences in JSON libraries cannot masquerade as numerical divergence. Rust passes
only a typed Sensors capability to Controller; truth/record bytes remain on the
plant/evaluation side. Metrics use the frozen Python evaluator. The exact IPC
operation layouts will be documented with the Rust implementation at B1.4.
