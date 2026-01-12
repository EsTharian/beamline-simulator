#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif

#include <signal.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

#include "config.h"
#include "devices.h"
#include "server.h"
#include "utils.h"

static volatile sig_atomic_t g_running = 1;
static volatile sig_atomic_t g_signal_received = 0;

static void signal_handler(int sig) {
    (void) sig;
    g_running = 0;
    g_signal_received = 1;
    // Don't call log_info here - it's not async-signal-safe
    // Logging will be done in main loop
}

int main(void) {
    log_init();
    devices_init();

    int listen_fd = server_init();
    if (listen_fd < 0) {
        log_error("Failed to initialize server");
        return EXIT_FAILURE;
    }

    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    log_info("Beamline simulator listening on port %d", BEAMLINE_PORT);

    struct timespec last_update = {0};
    clock_gettime(CLOCK_MONOTONIC, &last_update);

    while (g_running) {
        server_run_once(listen_fd);

        // Check if signal was received (async-signal-safe check)
        if (g_signal_received) {
            log_info("Received signal, shutting down...");
            g_signal_received = 0; // Reset flag
        }

        // Update devices every 10ms
        struct timespec now;
        clock_gettime(CLOCK_MONOTONIC, &now);
        double dt = ((double) (now.tv_sec - last_update.tv_sec)) +
                    ((double) (now.tv_nsec - last_update.tv_nsec) / 1e9);
        if (dt >= 0.01) {
            devices_update(dt);
            last_update = now;
        }

        // Small sleep to prevent 100% CPU
        nanosleep(&(struct timespec) {.tv_sec = 0, .tv_nsec = 1000000}, NULL); // 1ms
    }

    server_cleanup(listen_fd);
    log_info("Server shutdown complete");
    return EXIT_SUCCESS;
}
