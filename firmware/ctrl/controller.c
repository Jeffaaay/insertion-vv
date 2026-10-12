#include "controller.h"
#include <math.h>

#define N 7
#define TWO_PI 6.2831853071795864769f

size_t ctrl_state_size(void) { return sizeof(CtrlState); }
size_t ctrl_params_size(void) { return sizeof(CtrlParams); }
size_t ctrl_sensors_size(void) { return sizeof(CtrlSensors); }

void ctrl_default_params(CtrlParams *p) {
    *p = (CtrlParams){
        .kp = 10.0f, .kd = 0.2f, .initial_height = 1e-3f,
        .hover_height = 0.5e-3f, .depth = 0.3e-3f, .mass = 0.001f,
        .observer_position = 0.6f, .observer_velocity = 12.0f,
        .observer_acceleration = 400.0f, .frequencies = {1.2f, 2.4f, 0.25f},
        .initial_std = 500e-6f, .measurement_std = 2e-6f,
        .process_std = 0.2e-6f, .dt_us = 1000, .delay_us = 15000
    };
}

int ctrl_init(CtrlState *s, const CtrlParams *p) {
    if (!s || !p || p->dt_us != 1000 || p->delay_us != 15000 ||
        !(p->mass > 0.0f) || !(p->initial_std > 0.0f) ||
        !(p->measurement_std > 0.0f) || !(p->process_std >= 0.0f)) return -1;
    const float values[] = {p->kp, p->kd, p->initial_height, p->hover_height,
        p->depth, p->mass, p->observer_position, p->observer_velocity,
        p->observer_acceleration, p->frequencies[0], p->frequencies[1],
        p->frequencies[2], p->initial_std, p->measurement_std, p->process_std};
    for (size_t i = 0; i < sizeof(values) / sizeof(values[0]); ++i)
        if (!isfinite(values[i])) return -1;
    *s = (CtrlState){0};
    s->params = *p;
    for (int i = 0; i < N; ++i) s->root[i][i] = p->initial_std;
    return 0;
}

static void transition(const CtrlParams *p, uint32_t elapsed, float f[N][N]) {
    for (int i = 0; i < N; ++i)
        for (int j = 0; j < N; ++j) f[i][j] = i == j ? 1.0f : 0.0f;
    for (int i = 0; i < 3; ++i) {
        float phase = TWO_PI * p->frequencies[i] * ((float)elapsed * 1e-6f);
        float c = cosf(phase), sn = sinf(phase);
        int j = 1 + 2 * i;
        f[j][j] = c; f[j][j + 1] = sn;
        f[j + 1][j] = -sn; f[j + 1][j + 1] = c;
    }
}

static void matvec(float f[N][N], const float x[N], float out[N]) {
    for (int i = 0; i < N; ++i) {
        out[i] = 0.0f;
        for (int j = 0; j < N; ++j) out[i] += f[i][j] * x[j];
    }
}

/* Householder QR of A^T; L=R^T, so L L^T = A A^T. Fixed workspace,
   no covariance reconstruction/subtraction and no BLAS dependency. */
static int lower_root(int n, int cols, float a[8][14], float lower[8][8]) {
    float q[14][8] = {{0.0f}};
    for (int i = 0; i < cols; ++i)
        for (int j = 0; j < n; ++j) q[i][j] = a[j][i];
    for (int k = 0; k < n; ++k) {
        float norm = 0.0f;
        for (int i = k; i < cols; ++i) norm = hypotf(norm, q[i][k]);
        if (norm == 0.0f) continue;
        float old = q[k][k], alpha = -copysignf(norm, old);
        float divisor = old - alpha, tau = (alpha - old) / alpha;
        if (!isfinite(divisor) || divisor == 0.0f) return -1;
        q[k][k] = alpha;
        for (int i = k + 1; i < cols; ++i) q[i][k] /= divisor;
        for (int j = k + 1; j < n; ++j) {
            float dot = q[k][j];
            for (int i = k + 1; i < cols; ++i) dot += q[i][k] * q[i][j];
            dot *= tau;
            q[k][j] -= dot;
            for (int i = k + 1; i < cols; ++i) q[i][j] -= q[i][k] * dot;
        }
    }
    for (int i = 0; i < n; ++i)
        for (int j = 0; j < n; ++j) lower[i][j] = j <= i ? q[j][i] : 0.0f;
    return 0;
}

static int estimate(CtrlState *s, const CtrlSensors *in, float *position, float *velocity) {
    const CtrlParams *p = &s->params;
    float f[N][N], updated[N], a[8][14] = {{0.0f}}, lower[8][8];
    int fresh = (in->flags & (CTRL_SURFACE_VALID | CTRL_SURFACE_FRESH)) ==
                (CTRL_SURFACE_VALID | CTRL_SURFACE_FRESH);
    if (fresh && isfinite(in->surface_position) && in->time_us >= p->delay_us &&
        in->sample_time_us <= in->time_us - p->delay_us &&
        (!s->surface_ready || (in->sample_time_us > s->sample_time_us &&
                               in->sequence > s->sequence))) {
        if (s->surface_ready) {
            uint32_t elapsed = in->sample_time_us - s->sample_time_us;
            transition(p, elapsed, f);
            matvec(f, s->x, updated);
            float process_root = p->process_std * sqrtf((float)elapsed * 1e-6f);
            for (int i = 0; i < N; ++i) {
                s->x[i] = updated[i];
                for (int j = 0; j < N; ++j)
                    for (int k = 0; k < N; ++k) a[i][j] += f[i][k] * s->root[k][j];
                a[i][N + i] = process_root;
            }
            if (lower_root(N, 2 * N, a, lower)) return -1;
            for (int i = 0; i < N; ++i)
                for (int j = 0; j < N; ++j) s->root[i][j] = lower[i][j];
        }
        for (int i = 0; i < 8; ++i)
            for (int j = 0; j < 14; ++j) a[i][j] = 0.0f;
        a[0][0] = p->measurement_std;
        for (int j = 0; j < N; ++j) {
            a[0][j + 1] = s->root[0][j] + s->root[1][j] + s->root[3][j] + s->root[5][j];
            for (int i = 0; i < N; ++i) a[i + 1][j + 1] = s->root[i][j];
        }
        if (lower_root(N + 1, N + 1, a, lower) || lower[0][0] == 0.0f) return -1;
        float innovation = in->surface_position - (s->x[0] + s->x[1] + s->x[3] + s->x[5]);
        for (int i = 0; i < N; ++i) {
            s->x[i] += (lower[i + 1][0] / lower[0][0]) * innovation;
            for (int j = 0; j < N; ++j) s->root[i][j] = lower[i + 1][j + 1];
        }
        s->sample_time_us = in->sample_time_us; s->sequence = in->sequence;
        s->surface_ready = 1;
    }
    *position = 0.0f; *velocity = 0.0f;
    if (s->surface_ready) {
        transition(p, in->time_us - s->sample_time_us, f);
        matvec(f, s->x, updated);
        *position = updated[0] + updated[1] + updated[3] + updated[5];
        for (int i = 0; i < 3; ++i) *velocity += TWO_PI * p->frequencies[i] * updated[2 + 2 * i];
    }
    return 0;
}

static void smooth(float start, float end, float u, float duration, float *z, float *v) {
    float blend = u * u * (3.0f - 2.0f * u);
    *v = (end - start) * 6.0f * u * (1.0f - u) / duration;
    *z = start + (end - start) * blend;
}

static void reference(const CtrlParams *p, uint32_t time_us, float *z, float *v) {
    float t = (float)time_us / 1e6f;
    if (t < 1.0f) smooth(p->initial_height, p->hover_height, t, 1.0f, z, v);
    else if (t < 2.0f) { *z = p->hover_height; *v = 0.0f; }
    else if (t < 2.5f) smooth(p->hover_height, -p->depth, (t - 2.0f) / 0.5f, 0.5f, z, v);
    else { *z = -p->depth; *v = 0.0f; }
}

int ctrl_step(CtrlState *s, const CtrlSensors *in, CtrlCommand *out) {
    if (!s || !in || !out || in->tick != s->next_tick ||
        in->tick > UINT32_MAX / s->params.dt_us ||
        in->time_us != in->tick * s->params.dt_us ||
        (in->flags & ~3u) || !isfinite(in->needle_position) ||
        !isfinite(in->needle_velocity)) return -1;
    float dt = (float)s->params.dt_us * 1e-6f;
    if (!s->observer_ready) {
        s->observer_p = in->needle_position; s->observer_ready = 1;
    } else {
        float predicted_p = s->observer_p + dt * s->observer_v;
        float predicted_v = s->observer_v + dt * (s->observer_a + s->previous_force / s->params.mass);
        float innovation = in->needle_position - predicted_p;
        s->observer_p = predicted_p + s->params.observer_position * innovation;
        s->observer_v = predicted_v + s->params.observer_velocity * innovation;
        s->observer_a += s->params.observer_acceleration * innovation;
    }
    float surface_z, surface_v, gap, gap_v;
    if (estimate(s, in, &surface_z, &surface_v)) return -1;
    reference(&s->params, in->time_us, &gap, &gap_v);
    float force = s->params.kp * (gap + surface_z - in->needle_position)
        + s->params.kd * (gap_v + surface_v - in->needle_velocity);
    force -= s->params.mass * s->observer_a;
    if (!isfinite(force)) return -1;
    out->force = force; s->previous_force = force; ++s->next_tick;
    return 0;
}
