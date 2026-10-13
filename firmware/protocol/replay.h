#ifndef INSERTION_REPLAY_H
#define INSERTION_REPLAY_H
#include "protocol.h"

typedef struct {
    float force[VV_TICKS];
    uint32_t entry[VV_TICKS], compute[VV_TICKS];
    uint8_t status[VV_TICKS];
} VvTelemetry;
typedef struct {
    uint32_t entry_to_control[VV_TICKS], isr_body[VV_TICKS];
} VvTiming;

typedef struct {
    VvDevice *device;
    CtrlSensors *inputs;
    VvTelemetry *telemetry;
    VvTiming *timing;
    uint32_t loaded, completed, misses, overruns, isr_count;
    uint32_t input_crc, telemetry_crc, period, arm_low, arm_high, last_end;
    uint64_t elapsed_cycles;
    uint32_t previous_entry;
    volatile uint32_t state; /* 0 loading, 1 running/armed, 2 complete, 3 error */
    uint32_t mode, armed;
    uint32_t stack_free, stack_painted, fpscr, flash_crc, flash_bytes;
    uint32_t timing_crc;
} VvReplay;

/* CRC32/ISO-HDLC; call with 0xFFFFFFFF, complement after final chunk. */
uint32_t vv_crc32_update(uint32_t crc, const uint8_t *bytes, size_t count);
void vv_sensor_bytes(const CtrlSensors *input, uint8_t bytes[29]);
void vv_replay_init(VvReplay *r, VvDevice *device, CtrlSensors *inputs, VvTelemetry *telemetry,
                    VvTiming *timing);
void vv_replay_handle(VvReplay *r, const VvFrame *q, VvFrame *a, uint32_t (*cycles)(void));
void vv_replay_arm(VvReplay *r, uint32_t low, uint32_t high, uint32_t period);
void vv_replay_tick(VvReplay *r, uint32_t entry, uint32_t (*cycles)(void));
void vv_replay_exit(VvReplay *r, uint32_t exit_cycles, int update_pending);
void vv_replay_seal_telemetry(VvReplay *r);
#endif
