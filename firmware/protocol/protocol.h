#ifndef INSERTION_PROTOCOL_H
#define INSERTION_PROTOCOL_H
#include "../ctrl/controller.h"
#include <stddef.h>
#include <stdint.h>

enum { VV_MAX_PAYLOAD = 256, VV_MAX_FRAME = 268, VV_TICKS = 8000, VV_INFO_SIZE = 140 };
typedef struct {
    uint8_t type;
    uint32_t session;
    uint16_t length;
    uint8_t payload[VV_MAX_PAYLOAD];
} VvFrame;
typedef struct {
    CtrlState controller;
    uint8_t info[VV_INFO_SIZE];
    uint32_t session, next_tick;
    int active, finished;
} VvDevice;
uint16_t vv_crc(const uint8_t *data, size_t size);
uint32_t vv_u32(const uint8_t *p);
void vv_put32(uint8_t *p, uint32_t value);
int vv_decode(const uint8_t *wire, size_t size, VvFrame *frame);
size_t vv_encode(const VvFrame *frame, uint8_t *wire);
int vv_sensors(const uint8_t *payload, size_t length, CtrlSensors *input);
void vv_command(uint8_t *payload, uint32_t tick, float force, uint32_t entry, uint32_t compute,
                uint8_t status);
void vv_device_init(VvDevice *device, const uint8_t info[VV_INFO_SIZE]);
void vv_handle(VvDevice *device, const VvFrame *request, VvFrame *response,
               uint32_t (*cycles)(void));
#endif
