# NUCLEO-H723ZG build-only checkpoint

From the repository root with Arm GNU 14.2.rel1 installed:

```sh
python -m tools.build_firmware --output artifacts/h723-build --arm-cc /path/to/arm-none-eabi-gcc
```

This command never connects to or flashes a board. It fetches only the 48 selected
official ST/ARM files in `firmware/deps.lock.json`, verifies every SHA-256, and
caches them under `.toolchains/`. Reusing cached files still verifies their hashes.
The output directory must be empty. ELF/bin/map, per-function stack usage, ARM
attributes, build/clock/memory metadata and third-party dependency licenses are
retained. The build checks hard-float linkage, boot stack/reset vectors, actual
interrupt implementations, memory placement and absence of a dynamic allocator.

## Fixed hardware configuration

The configuration follows ST's pinned
[NUCLEO-H723ZG clock example](https://github.com/STMicroelectronics/STM32CubeH7/blob/8ec3113d4039d30ba9dc2bf0cb6eefc756b48d06/Projects/NUCLEO-H723ZG/Examples/BSP/Src/main.c)
at 520 MHz: 8 MHz HSE bypass from ST-LINK MCO, PLL M=4/N=260/P=1, LDO/VOS0,
AHB /2, all APBs /2, flash latency 3. This is below the H723's rated 550 MHz
maximum. The build does not establish that these clocks work on a connected board;
B2 must confirm boot, clock readback and INFO identity before measurements.

USART3 PD8/PD9 AF7 is the board's ST-LINK virtual COM port, 460800 8N1; use the
**ST-LINK CN1** USB connector as described in
[ST UM2407](https://www.st.com/resource/en/user_manual/um2407-stm32h7-nucleo144-board-stmicroelectronics.pdf).
RX uses DMA1 Stream0 / DMAMUX request 45 in circular mode, half/full/idle events and
a 512-byte D2 SRAM buffer. D-cache stays disabled; I-cache is enabled. No cacheable
DMA buffer or physical actuator output is configured. UART/DMA errors, overrun,
partial-frame timeout, bad CRC or invalid framing stop the firmware with a
debugger-readable `board_error`; resetting the board is then required.

TIM6 uses the 260 MHz APB1 timer clock, PSC=259 and ARR=999 for 1 kHz. In B1 it only
counts interrupts: lockstep control runs when a valid sensor frame arrives. INFO
advertises only lockstep, and replay requests receive unsupported status. DWT
records `ctrl_step` start and elapsed cycles; lockstep is a functional experiment,
not a real-time 1 kHz claim. Main may sleep between UART events, so entry-cycle
differences must not be treated as wall-clock interval measurements. B2 replay
must keep the CPU awake during its timed interval and use TIM-driven control.

The unchanged C32 core uses `-O2 -ffp-contract=off -fno-fast-math`, Cortex-M7
`-mfpu=fpv5-d16 -mfloat-abi=hard`, FPSCR=0 (nearest rounding, no flush-to-zero).
H723 supports both binary32 and binary64 hardware; C32 remains the registered
experimental choice. Vendor clock code is permitted to use double precision.
Metadata records compiler, all flags, linked libm archive hash, controller source
hash, firmware source hashes, ELF/bin hashes and dependency pins.

## Linker allocation

| Region | Allocation | Capacity / remaining |
|---|---|---|
| Flash, 0x08000000 | Code and initialized-data image | 1 MiB capacity |
| DTCM, 0x20000000 | State, 104000-byte telemetry, reserved 16384-byte stack | 128 KiB capacity; linker checks the gap |
| AXI, 0x24000000 | 8000 × 32-byte complete CtrlSensors = 256000 bytes | 320 KiB capacity, 71680 bytes spare |
| D2, 0x30000000 | 512-byte DMA RX buffer | 32 KiB capacity |

Code runs from Flash, not DTCM. The two replay arrays are reserved and kept by the
linker even though B1 does not execute replay; this tests the actual future budget.
NOLOAD buffers must be populated before use in B2. A 16 KiB stack reservation is
not a measured stack high-water mark. The linker's DTCM "100%" high-water line
includes the stack at the top of the bank; `build.json` reports the free gap
between data/telemetry and that stack separately.
