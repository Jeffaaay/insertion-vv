/* Loopback transport exercises the same frame handler later used by STM32. */
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
typedef SOCKET Socket;
#define CLOSE closesocket
#else
#include <arpa/inet.h>
#include <netinet/tcp.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
typedef int Socket;
#define INVALID_SOCKET (-1)
#define CLOSE close
#endif
#include "../protocol/protocol.h"
#include "build_identity.h"
#include <stdio.h>
#include <string.h>

static int receive(Socket socket, uint8_t *p, size_t count) {
    while (count) {
        int n = (int)recv(socket, (char *)p, (int)count, 0);
        if (n <= 0)
            return -1;
        p += n;
        count -= (size_t)n;
    }
    return 0;
}
static int send_all(Socket socket, const uint8_t *p, size_t count) {
    while (count) {
        int n = (int)send(socket, (const char *)p, (int)count, 0);
        if (n <= 0)
            return -1;
        p += n;
        count -= (size_t)n;
    }
    return 0;
}
int main(void) {
#ifdef _WIN32
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0)
        return 2;
#else
    signal(SIGPIPE, SIG_IGN);
#endif
    Socket listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener == INVALID_SOCKET)
        return 2;
    struct sockaddr_in address;
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    address.sin_port = 0;
    if (bind(listener, (struct sockaddr *)&address, sizeof(address)) || listen(listener, 1)) {
        CLOSE(listener);
        return 2;
    }
#ifdef _WIN32
    int address_size = sizeof(address);
#else
    socklen_t address_size = sizeof(address);
#endif
    if (getsockname(listener, (struct sockaddr *)&address, &address_size)) {
        CLOSE(listener);
        return 2;
    }
    printf("{\"port\":%u}\n", (unsigned)ntohs(address.sin_port));
    fflush(stdout);
    Socket peer = accept(listener, NULL, NULL);
    CLOSE(listener);
    if (peer == INVALID_SOCKET)
        return 2;
    int yes = 1;
    setsockopt(peer, IPPROTO_TCP, TCP_NODELAY, (const char *)&yes, sizeof(yes));
#ifdef _WIN32
    DWORD timeout = 5000;
#else
    struct timeval timeout = {5, 0};
#endif
    setsockopt(peer, SOL_SOCKET, SO_RCVTIMEO, (const char *)&timeout, sizeof(timeout));
    setsockopt(peer, SOL_SOCKET, SO_SNDTIMEO, (const char *)&timeout, sizeof(timeout));
    uint8_t info[VV_INFO_SIZE] = {0};
    info[1] = 1;
    info[2] = 1;
    vv_put32(info + 12, VV_TICKS);
    memcpy(info + 16, VV_BUILD_GIT, 40);
    memcpy(info + 56, VV_CONTROLLER_SOURCE_SHA256, 64);
    VvDevice device;
    vv_device_init(&device, info);
    int status = 2;
    while (!device.finished) {
        uint8_t wire[VV_MAX_FRAME];
        VvFrame request, response;
        if (receive(peer, wire, 10))
            break;
        size_t length = (size_t)wire[4] | ((size_t)wire[5] << 8);
        if (length > VV_MAX_PAYLOAD || receive(peer, wire + 10, length + 2) ||
            vv_decode(wire, length + 12, &request))
            break;
        vv_handle(&device, &request, &response, NULL);
        size_t count = vv_encode(&response, wire);
        if (!count || send_all(peer, wire, count))
            break;
    }
    if (device.finished)
        status = 0;
    else
        fputs("INVALID virtual board session\n", stderr);
    CLOSE(peer);
#ifdef _WIN32
    WSACleanup();
#endif
    return status;
}
