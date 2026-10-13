/* H723ZG: Flash execution, DTCM state/stack, AXI replay inputs, D2 DMA. */
ENTRY(Reset_Handler)
MEMORY {
    FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 1024K
    DTCM (rw) : ORIGIN = 0x20000000, LENGTH = 128K
    AXI (rw) : ORIGIN = 0x24000000, LENGTH = 320K
    D2 (rw) : ORIGIN = 0x30000000, LENGTH = 32K
}
_estack = ORIGIN(DTCM) + LENGTH(DTCM);
_stack_limit = _estack - 16K;
SECTIONS {
    .isr_vector : { . = ALIGN(512); KEEP(*(.isr_vector)) } > FLASH
    .text : { *(.text*) *(.rodata*) KEEP(*(.init)) KEEP(*(.fini)) . = ALIGN(4); } > FLASH
    .ARM.extab : { *(.ARM.extab* .gnu.linkonce.armextab.*) } > FLASH
    .ARM.exidx : { __exidx_start = .; *(.ARM.exidx*) __exidx_end = .; } > FLASH
    .preinit_array : {
        PROVIDE_HIDDEN(__preinit_array_start = .); KEEP(*(.preinit_array*))
        PROVIDE_HIDDEN(__preinit_array_end = .);
    } > FLASH
    .init_array : {
        PROVIDE_HIDDEN(__init_array_start = .); KEEP(*(SORT(.init_array.*))) KEEP(*(.init_array*))
        PROVIDE_HIDDEN(__init_array_end = .);
    } > FLASH
    .fini_array : {
        PROVIDE_HIDDEN(__fini_array_start = .); KEEP(*(SORT(.fini_array.*))) KEEP(*(.fini_array*))
        PROVIDE_HIDDEN(__fini_array_end = .);
    } > FLASH
    _sidata = LOADADDR(.data);
    .data : { . = ALIGN(4); _sdata = .; *(.data*) . = ALIGN(4); _edata = .; } > DTCM AT> FLASH
    _flash_image_end = LOADADDR(.data) + SIZEOF(.data);
    .bss (NOLOAD) : {
        . = ALIGN(4); _sbss = .; *(.bss*) *(COMMON) . = ALIGN(4); _ebss = .;
    } > DTCM
    .telemetry (NOLOAD) : { . = ALIGN(8); KEEP(*(.telemetry)) . = ALIGN(8); } > DTCM
    _dtcm_used_end = .;
    PROVIDE(end = .); PROVIDE(_end = .);
    .stack _stack_limit (NOLOAD) : { . += 16K; } > DTCM
    .replay_inputs (NOLOAD) : { . = ALIGN(32); KEEP(*(.replay_inputs)) . = ALIGN(32); } > AXI
    .replay_timing (NOLOAD) : { . = ALIGN(8); KEEP(*(.replay_timing)) . = ALIGN(8); } > AXI
    .dma (NOLOAD) : { . = ALIGN(32); KEEP(*(.dma)) . = ALIGN(32); } > D2
    .ARM.attributes 0 : { *(.ARM.attributes) }
    /DISCARD/ : { *(.comment) *(.note.GNU-stack) }
}
ASSERT(_dtcm_used_end <= _stack_limit, "DTCM state/telemetry overlaps reserved 16 KiB stack")
ASSERT(SIZEOF(.replay_inputs) == 256000, "8000 full Sensors must occupy 256000 bytes")
ASSERT(SIZEOF(.telemetry) == 104000, "8000 telemetry records must occupy 104000 bytes")
ASSERT(SIZEOF(.replay_timing) == 64000, "8000 timing breakdowns must occupy 64000 bytes")
ASSERT(SIZEOF(.dma) <= LENGTH(D2), "DMA buffer exceeds D2 SRAM")
