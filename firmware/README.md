Phase B begins with the [portable C32 controller](ctrl/README.md), shared by host
tests and the later H723 firmware. The MCU image and hardware runs follow separate
checkpoints in [the preregistered plan](../docs/PHASE_B_PLAN.md). Compiling an ARM
object is not a board test; no hardware success is claimed yet.

The [H723 image](h723/README.md) now links the unchanged C core and the same
portable protocol handler used by the C virtual board. It includes USART3 RX DMA,
DWT measurements and a TIM6 1 kHz heartbeat; board replay remains the B2 step.
CI builds the complete image, checks memory reservations/boot vectors/hard-float
ABI, and retains ELF, binary, map, stack-usage files and exact dependency licenses.
