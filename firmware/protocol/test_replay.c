/* Synthetic clocks exercise correctness only; never hardware timing evidence.
 */
#include "replay.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static CtrlSensors inputs[VV_TICKS];
static VvTelemetry telemetry;
static VvTiming timing;
static VvDevice device;
static VvReplay replay;
static uint32_t fake;
static uint32_t clock_read(void) {
    uint32_t value = fake;
    fake += 26000;
    return value;
}
static VvFrame request(uint8_t type, uint16_t length) {
    VvFrame q = {0};
    q.type = type;
    q.session = 19;
    q.length = length;
    return q;
}
static void reset(void) {
    uint8_t info[VV_INFO_SIZE] = {0};
    vv_device_init(&device, info);
    vv_replay_init(&replay, &device, inputs, &telemetry, &timing);
    VvFrame q = request(2, 5), a;
    q.payload[0] = 1;
    vv_put32(q.payload + 1, VV_TICKS);
    vv_replay_handle(&replay, &q, &a, NULL);
    assert(a.type == 0x82 && a.payload[1] == 0 && replay.mode == 1);
}
static uint32_t load(void) {
    uint32_t crc = 0xffffffffu;
    for (uint32_t tick = 0; tick < VV_TICKS; tick++) {
        CtrlSensors s = {0};
        s.tick = tick;
        s.time_us = tick * 1000u;
        s.needle_position = 0.001f;
        if (tick >= 15) {
            s.sample_time_us = (tick - 15) * 1000;
            s.sequence = tick - 15;
            s.flags = 3;
            s.surface_position = 0.0001f;
        }
        VvFrame q = request(5, 29), a;
        vv_sensor_bytes(&s, q.payload);
        crc = vv_crc32_update(crc, q.payload, 29);
        vv_replay_handle(&replay, &q, &a, NULL);
        assert(a.type == 0x85 && vv_u32(a.payload) == tick && a.payload[4] == 0);
        assert(device.controller.next_tick == 0); /* Upload never runs control. */
    }
    return ~crc;
}
static void start(uint32_t crc) {
    VvFrame q = request(6, 4), a;
    vv_put32(q.payload, crc);
    vv_replay_handle(&replay, &q, &a, NULL);
    assert(a.payload[1] == 0 && replay.armed);
}
int main(void) {
    assert(~vv_crc32_update(0xffffffffu, (const uint8_t *)"123456789", 9) == 0xcbf43926u);
    reset();
    VvFrame q = request(6, 4), a;
    vv_replay_handle(&replay, &q, &a, NULL);
    assert(a.payload[1] == 6 && replay.state == 0);
    uint32_t crc = load();
    inputs[444].needle_position = 0.002f; /* Valid envelope cannot hide RAM/input damage. */
    vv_put32(q.payload, crc);
    vv_replay_handle(&replay, &q, &a, NULL);
    assert(a.payload[1] == 1 && replay.state == 3);

    reset();
    crc = load();
    q = request(9, 0);
    vv_replay_handle(&replay, &q, &a, NULL);
    assert(a.type == 0x89 && vv_u32(a.payload + 16) == crc);
    start(crc);
    const uint32_t epoch = 0xffff0000u, period = 520000u;
    vv_replay_arm(&replay, epoch, epoch + 20, period);
    CtrlParams params;
    CtrlState reference;
    ctrl_default_params(&params);
    assert(ctrl_init(&reference, &params) == 0);
    for (uint32_t k = 0; k < VV_TICKS; k++) {
        uint32_t entry = epoch + (k + 1) * period + 200;
        fake = entry + 30;
        vv_replay_tick(&replay, entry, clock_read);
        vv_replay_exit(&replay, entry + 26100, 0);
        CtrlCommand expected;
        assert(ctrl_step(&reference, &inputs[k], &expected) == 0);
        assert(memcmp(&expected.force, &telemetry.force[k], 4) == 0);
        assert(telemetry.compute[k] == 26000 && telemetry.status[k] == 0);
        assert(timing.entry_to_control[k] == 30 && timing.isr_body[k] == 26100);
    }
    assert(replay.state == 2 && replay.completed == VV_TICKS && replay.isr_count == VV_TICKS);
    assert(replay.misses == 0 && replay.overruns == 0);
    vv_replay_seal_telemetry(&replay);
    uint32_t fetched_crc = 0xffffffffu;
    uint32_t timing_crc = 0xffffffffu;
    for (uint32_t k = 0; k < VV_TICKS; k += 10) {
        q = request(8, 6);
        vv_put32(q.payload, k);
        q.payload[4] = 10;
        vv_replay_handle(&replay, &q, &a, NULL);
        assert(a.type == 0x88 && a.length == 176 && vv_u32(a.payload) == k);
        fetched_crc = vv_crc32_update(fetched_crc, a.payload + 6, 170);
        q.type = 10;
        vv_replay_handle(&replay, &q, &a, NULL);
        assert(a.type == 0x8a && a.length == 86 && vv_u32(a.payload) == k);
        timing_crc = vv_crc32_update(timing_crc, a.payload + 6, 80);
    }
    assert(~fetched_crc == replay.telemetry_crc);
    assert(~timing_crc == replay.timing_crc);
    q = request(8, 6);
    vv_put32(q.payload, VV_TICKS - 1);
    q.payload[4] = 10;
    vv_replay_handle(&replay, &q, &a, NULL);
    assert(a.type == 0x82 && a.payload[1] != 0);
    q = request(4, 4);
    vv_put32(q.payload, VV_TICKS);
    vv_replay_handle(&replay, &q, &a, NULL);
    assert(a.payload[1] == 0 && device.finished);

    reset();
    crc = load();
    start(crc);
    vv_replay_arm(&replay, epoch, epoch + 20, period);
    fake = epoch + period + 100;
    vv_replay_tick(&replay, epoch + period + 50, clock_read);
    vv_replay_exit(&replay, epoch + period + 26200, 1);
    assert(replay.misses == 1 && replay.overruns == 1 && telemetry.status[0] == 0x80);
    /* Coalesced/delayed entry, even without UIF at exit, misses absolute
     * deadline. */
    fake = epoch + 4 * period;
    vv_replay_tick(&replay, epoch + 4 * period, clock_read);
    vv_replay_exit(&replay, epoch + 4 * period + 26200, 0);
    assert(replay.misses == 2 && telemetry.status[1] == 0x80);
    reset();
    q = request(5, 29);
    vv_put32(q.payload, 1);
    vv_replay_handle(&replay, &q, &a, NULL);
    assert(a.payload[4] == 2 && replay.state == 3);
    puts("PASS replay CRC, ordering, state, 8000 bitwise commands, modular "
         "clocks and deadline tests (synthetic)");
    return 0;
}
