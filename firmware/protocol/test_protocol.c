#include "protocol.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
    assert(vv_crc((const uint8_t *)"123456789", 9) == 0x29b1u);
    assert(argc == 6);
    for (int arg = 1; arg < argc; arg++) {
        uint8_t wire[VV_MAX_FRAME], encoded[VV_MAX_FRAME], corrupt[VV_MAX_FRAME];
        size_t n = strlen(argv[arg]) / 2;
        assert(n <= VV_MAX_FRAME && strlen(argv[arg]) == n * 2);
        for (size_t i = 0; i < n; i++) {
            unsigned value;
            assert(sscanf(argv[arg] + i * 2, "%2x", &value) == 1);
            wire[i] = (uint8_t)value;
        }
        VvFrame frame;
        assert(vv_decode(wire, n, &frame) == 0);
        assert(vv_encode(&frame, encoded) == n);
        assert(memcmp(wire, encoded, n) == 0);
        for (size_t i = 0; i < n; i++)
            assert(vv_decode(wire, i, &frame) != 0);
        for (size_t bit = 0; bit < n * 8; bit++) {
            memcpy(corrupt, wire, n);
            corrupt[bit / 8] ^= (uint8_t)(1u << (bit % 8));
            assert(vv_decode(corrupt, n, &frame) != 0);
        }
    }
    uint8_t info[VV_INFO_SIZE] = {0};
    VvDevice device;
    VvFrame request = {0}, response;
    vv_device_init(&device, info);
    request.type = 2;
    request.session = 123;
    request.length = 5;
    vv_put32(request.payload + 1, VV_TICKS);
    vv_handle(&device, &request, &response, NULL);
    assert(response.payload[1] == 0);
    vv_handle(&device, &request, &response, NULL);
    assert(response.payload[1] == 2);
    request.type = 4;
    request.length = 4;
    vv_put32(request.payload, VV_TICKS);
    vv_handle(&device, &request, &response, NULL);
    assert(response.payload[1] == 6 && !device.active);
    request.type = 2;
    request.session = 124;
    request.length = 5;
    request.payload[0] = 1;
    vv_put32(request.payload + 1, VV_TICKS);
    vv_handle(&device, &request, &response, NULL);
    assert(response.payload[1] == 3);
    puts("C protocol: golden frames, corruption/truncation, sessions, incomplete finish, "
         "unsupported replay: PASS");
    return 0;
}
