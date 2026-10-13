#include "protocol.h"
#include <float.h>
#include <math.h>
#include <string.h>
_Static_assert(sizeof(float) == 4 && FLT_RADIX == 2 && FLT_MANT_DIG == 24,
               "IEEE binary32 required");

uint16_t vv_crc(const uint8_t *data, size_t size) {
    uint16_t crc = 0xffffu;
    for (size_t i = 0; i < size; i++) {
        crc ^= (uint16_t)((uint16_t)data[i] << 8);
        for (unsigned bit = 0; bit < 8; bit++)
            crc = (uint16_t)((crc & 0x8000u) ? ((uint32_t)crc << 1) ^ 0x1021u : (uint32_t)crc << 1);
    }
    return crc;
}
uint32_t vv_u32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
void vv_put32(uint8_t *p, uint32_t value) {
    for (unsigned i = 0; i < 4; i++)
        p[i] = (uint8_t)(value >> (i * 8));
}
static float number(const uint8_t *p) {
    uint32_t bits = vv_u32(p);
    float value;
    memcpy(&value, &bits, 4);
    return value;
}
static void put_float(uint8_t *p, float value) {
    uint32_t bits;
    memcpy(&bits, &value, 4);
    vv_put32(p, bits);
}
int vv_decode(const uint8_t *wire, size_t size, VvFrame *frame) {
    if (size < 12 || wire[0] != 0xa5 || wire[1] != 0x5a || wire[2] != 1)
        return -1;
    uint16_t n = (uint16_t)((uint16_t)wire[4] | ((uint16_t)wire[5] << 8));
    if (n > VV_MAX_PAYLOAD || size != (size_t)n + 12)
        return -1;
    uint16_t crc = (uint16_t)((uint16_t)wire[size - 2] | ((uint16_t)wire[size - 1] << 8));
    if (crc != vv_crc(wire + 2, size - 4))
        return -1;
    uint8_t type = wire[3];
    if (!((type >= 1 && type <= 10) || (type >= 0x81 && type <= 0x83) || type == 0x85 ||
          (type >= 0x87 && type <= 0x8a)))
        return -1;
    frame->type = wire[3];
    frame->session = vv_u32(wire + 6);
    frame->length = n;
    memcpy(frame->payload, wire + 10, n);
    return 0;
}
size_t vv_encode(const VvFrame *frame, uint8_t *wire) {
    if (frame->length > VV_MAX_PAYLOAD)
        return 0;
    size_t size = (size_t)frame->length + 12;
    wire[0] = 0xa5;
    wire[1] = 0x5a;
    wire[2] = 1;
    wire[3] = frame->type;
    wire[4] = (uint8_t)frame->length;
    wire[5] = (uint8_t)(frame->length >> 8);
    vv_put32(wire + 6, frame->session);
    memcpy(wire + 10, frame->payload, frame->length);
    uint16_t crc = vv_crc(wire + 2, size - 4);
    wire[size - 2] = (uint8_t)crc;
    wire[size - 1] = (uint8_t)(crc >> 8);
    return size;
}
int vv_sensors(const uint8_t *p, size_t length, CtrlSensors *input) {
    if (length != 29 || (p[28] != 0 && p[28] != 1 && p[28] != 3))
        return -1;
    input->tick = vv_u32(p);
    input->time_us = vv_u32(p + 4);
    input->sample_time_us = vv_u32(p + 8);
    input->sequence = vv_u32(p + 12);
    input->needle_position = number(p + 16);
    input->needle_velocity = number(p + 20);
    input->surface_position = number(p + 24);
    input->flags = p[28];
    if (!isfinite(input->needle_position) || !isfinite(input->needle_velocity) ||
        !isfinite(input->surface_position))
        return -1;
    if (input->flags == 0 &&
        (input->sample_time_us != 0 || input->sequence != 0 || vv_u32(p + 24) != 0))
        return -1;
    return 0;
}
void vv_command(uint8_t *p, uint32_t tick, float force, uint32_t entry, uint32_t compute,
                uint8_t status) {
    vv_put32(p, tick);
    put_float(p + 4, force);
    vv_put32(p + 8, entry);
    vv_put32(p + 12, compute);
    p[16] = status;
}
void vv_device_init(VvDevice *device, const uint8_t info[VV_INFO_SIZE]) {
    memset(device, 0, sizeof(*device));
    memcpy(device->info, info, VV_INFO_SIZE);
}
void vv_handle(VvDevice *device, const VvFrame *request, VvFrame *response,
               uint32_t (*cycles)(void)) {
    memset(response, 0, sizeof(*response));
    response->type = 0x82;
    response->session = request->session;
    response->length = 2;
    response->payload[0] = request->type;
    response->payload[1] = 1;
    if (request->type == 1) {
        if (request->session != 0 || request->length != 0)
            return;
        response->type = 0x81;
        response->length = VV_INFO_SIZE;
        memcpy(response->payload, device->info, VV_INFO_SIZE);
        return;
    }
    if (request->type == 2) {
        if (request->length != 5 || vv_u32(request->payload + 1) != VV_TICKS ||
            request->session == 0)
            return;
        if (request->payload[0] != 0) {
            response->payload[1] = 3;
            return;
        }
        if (request->session == device->session) {
            response->payload[1] = 2;
            return;
        }
        CtrlParams params;
        ctrl_default_params(&params);
        if (ctrl_init(&device->controller, &params) != 0) {
            response->payload[1] = 4;
            return;
        }
        device->session = request->session;
        device->next_tick = 0;
        device->active = 1;
        device->finished = 0;
        response->payload[1] = 0;
        return;
    }
    if (request->type == 3) {
        CtrlSensors input;
        CtrlCommand output = {0.0f};
        uint8_t status = 0;
        uint32_t entry = 0, compute = 0;
        uint32_t tick = request->length >= 4 ? vv_u32(request->payload) : 0;
        if (vv_sensors(request->payload, request->length, &input) != 0)
            status = 1;
        else if (!device->active || request->session != device->session ||
                 input.tick != device->next_tick || input.tick >= VV_TICKS ||
                 input.time_us != input.tick * 1000u)
            status = 2;
        else {
            if (cycles)
                entry = cycles();
            int result = ctrl_step(&device->controller, &input, &output);
            if (cycles)
                compute = cycles() - entry;
            if (result != 0 || !isfinite(output.force)) {
                status = 4;
                output.force = 0.0f;
            }
        }
        if (status)
            device->active = 0;
        else
            device->next_tick++;
        response->type = 0x83;
        response->length = 17;
        vv_command(response->payload, tick, output.force, entry, compute, status);
        return;
    }
    if (request->type == 4) {
        if (request->length != 4)
            return;
        if (request->session != device->session || !device->active) {
            response->payload[1] = 2;
            return;
        }
        if (vv_u32(request->payload) != VV_TICKS || device->next_tick != VV_TICKS) {
            response->payload[1] = 6;
            device->active = 0;
            return;
        }
        device->active = 0;
        device->finished = 1;
        response->payload[1] = 0;
        return;
    }
    response->payload[1] = 3; /* B1 does not advertise replay capability. */
}
