/* Portable replay state machine; hardware provides clocks and IRQ scheduling.
 */
#include "replay.h"
#include <math.h>
#include <string.h>
_Static_assert(sizeof(CtrlSensors) == 32 && sizeof(VvTelemetry) == 104000, "replay RAM budget");

uint32_t vv_crc32_update(uint32_t crc, const uint8_t *bytes, size_t count) {
    for (size_t i = 0; i < count; i++) {
        crc ^= bytes[i];
        for (unsigned j = 0; j < 8; j++)
            crc = (crc >> 1) ^ ((crc & 1u) ? 0xedb88320u : 0u);
    }
    return crc;
}
void vv_sensor_bytes(const CtrlSensors *s, uint8_t p[29]) {
    vv_put32(p, s->tick);
    vv_put32(p + 4, s->time_us);
    vv_put32(p + 8, s->sample_time_us);
    vv_put32(p + 12, s->sequence);
    uint32_t bits;
    memcpy(&bits, &s->needle_position, 4);
    vv_put32(p + 16, bits);
    memcpy(&bits, &s->needle_velocity, 4);
    vv_put32(p + 20, bits);
    memcpy(&bits, &s->surface_position, 4);
    vv_put32(p + 24, bits);
    p[28] = (uint8_t)s->flags;
}
static uint32_t input_crc(VvReplay *r) {
    uint32_t crc = 0xffffffffu;
    for (uint32_t i = 0; i < r->loaded; i++) {
        uint8_t bytes[29];
        vv_sensor_bytes(&r->inputs[i], bytes);
        crc = vv_crc32_update(crc, bytes, sizeof(bytes));
    }
    return ~crc;
}
void vv_replay_init(VvReplay *r, VvDevice *device, CtrlSensors *inputs, VvTelemetry *telemetry,
                    VvTiming *timing) {
    memset(r, 0, sizeof(*r));
    r->device = device;
    r->inputs = inputs;
    r->telemetry = telemetry;
    r->timing = timing;
}
static void ack(const VvFrame *q, VvFrame *a, uint8_t status) {
    memset(a, 0, sizeof(*a));
    a->type = 0x82;
    a->session = q->session;
    a->length = 2;
    a->payload[0] = q->type;
    a->payload[1] = status;
}
static void summary(VvReplay *r, VvFrame *a) {
    /* Polled after completion, never unsolicited traffic in the timed interval.
     */
    if (r->state == 0)
        r->input_crc = input_crc(r);
    a->type = 0x89;
    a->length = 84;
    uint32_t words[20] = {r->state,
                          r->loaded,
                          r->completed,
                          r->misses,
                          r->input_crc,
                          r->telemetry_crc,
                          r->isr_count,
                          r->arm_low,
                          r->arm_high,
                          r->last_end,
                          r->stack_free,
                          r->stack_painted,
                          r->fpscr,
                          vv_u32(r->device->info + 4),
                          vv_u32(r->device->info + 8),
                          5u, /* I-cache on, D-cache off, awake replay */
                          r->flash_crc,
                          r->flash_bytes,
                          r->overruns,
                          r->period};
    for (unsigned i = 0; i < 20; i++)
        vv_put32(a->payload + 4 * i, words[i]);
    vv_put32(a->payload + 80, r->timing_crc);
}
void vv_replay_handle(VvReplay *r, const VvFrame *q, VvFrame *a, uint32_t (*cycles)(void)) {
    if (q->type == 1) {
        vv_handle(r->device, q, a, cycles);
        return;
    }
    ack(q, a, 1);
    if (q->type == 2) {
        if (r->state == 1) {
            a->payload[1] = 2;
            return;
        }
        if (q->length != 5 || q->payload[0] > 1)
            return;
        VvFrame reset = *q;
        reset.payload[0] = 0;
        vv_handle(r->device, &reset, a, cycles);
        if (a->payload[1] == 0) {
            VvDevice *d = r->device;
            CtrlSensors *inputs = r->inputs;
            VvTelemetry *t = r->telemetry;
            VvTiming *timing = r->timing;
            vv_replay_init(r, d, inputs, t, timing);
            r->mode = q->payload[0];
        }
        return;
    }
    if (!r->mode) {
        vv_handle(r->device, q, a, cycles);
        return;
    }
    if (!q->session || q->session != r->device->session) {
        a->payload[1] = 2;
        r->state = 3;
        return;
    }
    if (q->type == 5) {
        uint8_t status = 0;
        CtrlSensors s;
        uint32_t tick = q->length >= 4 ? vv_u32(q->payload) : 0;
        if (vv_sensors(q->payload, q->length, &s))
            status = 1;
        else if (r->state != 0 || r->loaded >= VV_TICKS || s.tick != r->loaded ||
                 s.time_us != s.tick * 1000u)
            status = 2;
        if (status)
            r->state = 3;
        else
            r->inputs[r->loaded++] = s;
        a->type = 0x85;
        a->length = 5;
        vv_put32(a->payload, tick);
        a->payload[4] = status;
        return;
    }
    if (q->type == 6) {
        if (q->length != 4)
            return;
        if (r->state != 0 || r->loaded != VV_TICKS) {
            a->payload[1] = 6;
            return;
        }
        r->input_crc = input_crc(r);
        if (vv_u32(q->payload) != r->input_crc) {
            r->state = 3;
            a->payload[1] = 1;
            return;
        }
        CtrlParams p;
        ctrl_default_params(&p);
        if (ctrl_init(&r->device->controller, &p)) {
            r->state = 3;
            a->payload[1] = 4;
            return;
        }
        r->state = 1;
        r->armed = 1;
        a->payload[1] = 0;
        return;
    }
    if (q->type == 7 && q->length == 0) {
        a->type = 0x87;
        a->length = 9;
        a->payload[0] = (uint8_t)r->state;
        vv_put32(a->payload + 1, r->completed);
        vv_put32(a->payload + 5, r->misses);
        return;
    }
    if (q->type == 9 && q->length == 0 && r->state != 1) {
        summary(r, a);
        return;
    }
    if ((q->type == 8 || q->type == 10) && q->length == 6 && (r->state == 2 || r->state == 3)) {
        uint32_t first = vv_u32(q->payload);
        unsigned count = (unsigned)q->payload[4] | ((unsigned)q->payload[5] << 8);
        if (!count || count > 10 || first >= r->completed || count > r->completed - first)
            return;
        a->type = q->type == 8 ? 0x88 : 0x8a;
        a->length = (uint16_t)(6 + (q->type == 8 ? 17 : 8) * count);
        memcpy(a->payload, q->payload, 6);
        for (unsigned i = 0; i < count; i++) {
            uint32_t k = first + i;
            if (q->type == 8)
                vv_command(a->payload + 6 + 17 * i, k, r->telemetry->force[k],
                           r->telemetry->entry[k], r->telemetry->compute[k],
                           r->telemetry->status[k]);
            else {
                vv_put32(a->payload + 6 + 8 * i, r->timing->entry_to_control[k]);
                vv_put32(a->payload + 10 + 8 * i, r->timing->isr_body[k]);
            }
        }
        return;
    }
    if (q->type == 4 && q->length == 4 && vv_u32(q->payload) == VV_TICKS && r->state == 2 &&
        r->completed == VV_TICKS) {
        r->device->finished = 1;
        r->device->active = 0;
        a->payload[1] = 0;
        return;
    }
    a->payload[1] = 2;
}
void vv_replay_arm(VvReplay *r, uint32_t low, uint32_t high, uint32_t period) {
    r->arm_low = low;
    r->arm_high = high;
    r->previous_entry = low;
    r->elapsed_cycles = 0;
    r->period = period;
    r->armed = 0;
}
void vv_replay_tick(VvReplay *r, uint32_t entry, uint32_t (*cycles)(void)) {
    if (r->state != 1 || r->armed || r->completed >= VV_TICKS)
        return;
    uint32_t k = r->completed;
    r->isr_count++;
    r->elapsed_cycles += (uint32_t)(entry - r->previous_entry);
    r->previous_entry = entry;
    r->telemetry->entry[k] = entry;
    CtrlCommand output = {0.0f};
    uint32_t start = cycles();
    int result = ctrl_step(&r->device->controller, &r->inputs[k], &output);
    uint32_t end = cycles();
    r->timing->entry_to_control[k] = start - entry;
    r->telemetry->compute[k] = end - start;
    r->telemetry->status[k] = (result || !isfinite(output.force)) ? 4u : 0u;
    r->telemetry->force[k] = result ? 0.0f : output.force;
}
void vv_replay_exit(VvReplay *r, uint32_t exit_cycles, int update_pending) {
    if (r->state != 1 || r->armed || r->completed >= VV_TICKS)
        return;
    uint32_t k = r->completed;
    uint64_t end = r->elapsed_cycles + (uint32_t)(exit_cycles - r->previous_entry);
    if (update_pending)
        r->overruns++;
    if (update_pending || r->telemetry->compute[k] >= r->period ||
        end >= (uint64_t)(k + 2u) * r->period) {
        r->telemetry->status[k] |= 0x80;
        r->misses++;
    }
    r->last_end = exit_cycles;
    r->timing->isr_body[k] = exit_cycles - r->previous_entry;
    r->completed++;
    if (r->telemetry->status[k] & 0x7f)
        r->state = 3;
    else if (r->completed == VV_TICKS)
        r->state = 2;
}
void vv_replay_seal_telemetry(VvReplay *r) {
    uint32_t crc = 0xffffffffu;
    uint32_t timing_crc = 0xffffffffu;
    for (uint32_t k = 0; k < r->completed; k++) {
        uint8_t p[17];
        vv_command(p, k, r->telemetry->force[k], r->telemetry->entry[k], r->telemetry->compute[k],
                   r->telemetry->status[k]);
        crc = vv_crc32_update(crc, p, sizeof(p));
        uint8_t t[8];
        vv_put32(t, r->timing->entry_to_control[k]);
        vv_put32(t + 4, r->timing->isr_body[k]);
        timing_crc = vv_crc32_update(timing_crc, t, sizeof(t));
    }
    r->telemetry_crc = ~crc;
    r->timing_crc = ~timing_crc;
}
