#ifndef INSERTION_CONTROLLER_H
#define INSERTION_CONTROLLER_H

#include <stdint.h>
#include <stddef.h>

#if defined(_WIN32) && defined(CTRL_SHARED)
#define CTRL_API __declspec(dllexport)
#else
#define CTRL_API
#endif

enum { CTRL_SURFACE_VALID = 1, CTRL_SURFACE_FRESH = 2 };

typedef struct {
    float kp, kd, initial_height, hover_height, depth;
    float mass, observer_position, observer_velocity, observer_acceleration;
    float frequencies[3], initial_std, measurement_std, process_std;
    uint32_t dt_us, delay_us;
} CtrlParams;

/* Controller capability only: no plant, contact force, or evaluator truth. */
typedef struct {
    uint32_t tick, time_us, sample_time_us, sequence;
    float needle_position, needle_velocity, surface_position;
    uint32_t flags;
} CtrlSensors;

typedef struct { float force; } CtrlCommand;

typedef struct {
    CtrlParams params;
    float x[7], root[7][7];
    float observer_p, observer_v, observer_a, previous_force;
    uint32_t sample_time_us, sequence, next_tick;
    uint32_t observer_ready, surface_ready;
} CtrlState;

CTRL_API void ctrl_default_params(CtrlParams *params);
CTRL_API int ctrl_init(CtrlState *state, const CtrlParams *params);
/* Return 0 for a command, -1 for invalid input/numerical failure. No allocation. */
CTRL_API int ctrl_step(CtrlState *state, const CtrlSensors *sensors, CtrlCommand *command);
CTRL_API size_t ctrl_state_size(void);
CTRL_API size_t ctrl_params_size(void);
CTRL_API size_t ctrl_sensors_size(void);

#endif
