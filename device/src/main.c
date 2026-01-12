#include <stdio.h>
#include <stdlib.h>

#include "config.h"

int main(void) {
    printf("Beamline Device Simulator v0.1.0\n");
    printf("Port: %d\n", BEAMLINE_PORT);
    printf("Max clients: %d\n", BEAMLINE_MAX_CLIENTS);

    // TODO: Initialize server (M2)
    // TODO: Start event loop (M2)

    return EXIT_SUCCESS;
}
