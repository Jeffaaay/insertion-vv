/* Independent invariants for the numerical core, not nominal plant acceptance. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "controller.c"

static void test_root(void) {
    float a[8][14] = {{0.0f}}, l[8][8];
    for (int i = 0; i < 7; ++i) {
        a[i][i] = (float)(i + 1) * 1e-4f;
        a[i][7 + i] = 1e-7f;
        a[i][0] += 2e-5f;
    }
    assert(lower_root(7, 14, a, l) == 0);
    for (int i = 0; i < 7; ++i) for (int j = 0; j < 7; ++j) {
        double expected = 0.0, actual = 0.0;
        for (int k = 0; k < 14; ++k) expected += (double)a[i][k] * (double)a[j][k];
        for (int k = 0; k < 7; ++k) actual += (double)l[i][k] * (double)l[j][k];
        assert(fabs(expected - actual) < 1e-12);
        if (j > i) assert(l[i][j] == 0.0f);
    }
}

static void test_api_and_freshness(void) {
    CtrlParams p; ctrl_default_params(&p);
    CtrlState a, b, saved; CtrlCommand ca, cb;
    assert(ctrl_init(&a, &p) == 0); b = a;
    CtrlSensors in = {.needle_position = p.initial_height};
    assert(ctrl_step(&a, &in, &ca) == 0 && ca.force == 0.0f);
    assert(ctrl_step(&b, &in, &cb) == 0 && memcmp(&a, &b, sizeof(a)) == 0);
    saved = a;
    assert(ctrl_step(&a, &in, &ca) == -1);
    assert(memcmp(&a, &saved, sizeof(a)) == 0);
    for (uint32_t tick = 1; tick < 100; ++tick) {
        in.tick = tick; in.time_us = tick * 1000;
        in.flags = CTRL_SURFACE_VALID | CTRL_SURFACE_FRESH;
        in.sample_time_us = 0; in.sequence = 0; in.surface_position = 1e-5f;
        CtrlSensors other = in;
        /* Both reject early delivery; after first delivery they ignore held IDs. */
        if (tick != 15) other.surface_position = 0.02f;
        assert(ctrl_step(&a, &in, &ca) == 0);
        assert(ctrl_step(&b, &other, &cb) == 0);
        assert(ca.force == cb.force && memcmp(&a, &b, sizeof(a)) == 0);
    }
    in.tick = 100; in.time_us = 100000; in.needle_velocity = NAN;
    saved = a;
    assert(ctrl_step(&a, &in, &ca) == -1 && memcmp(&a, &saved, sizeof(a)) == 0);
    assert(ctrl_state_size() == sizeof(a));
    assert(ctrl_params_size() == sizeof(p));
    assert(ctrl_sensors_size() == sizeof(in));
}

int main(void) {
    test_root(); test_api_and_freshness();
    puts("C core: QR Gram residual, repeatability, fresh/held/early frames, invalid tick/nonfinite input: PASS");
    return 0;
}
