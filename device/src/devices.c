#include "devices.h"

#include <math.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "utils.h"

// Global registry
static pv_t g_pvs[BEAMLINE_MAX_PVS];
static int g_pv_count = 0;
static motor_t g_motors[8]; // X, Y, Z, THETA, MONO:ENERGY, etc.
static int g_motor_count = 0;

// Internal helper to register a PV (using named parameters struct)
static pv_t *pv_register(pv_register_params_t params) {
    if (g_pv_count >= BEAMLINE_MAX_PVS) {
        log_error("PV registry full, cannot register: %s", params.name);
        return NULL;
    }

    pv_t *pv = &g_pvs[g_pv_count++];
    strncpy(pv->name, params.name, BEAMLINE_PV_NAME_MAX - 1);
    pv->name[BEAMLINE_PV_NAME_MAX - 1] = '\0';
    pv->type = params.type;
    pv->value = 0.0;
    pv->min = params.range.min;
    pv->max = params.range.max;
    pv->writable = params.writable;
    pv->update_fn = params.update_fn;

    return pv;
}

// Sensor update functions
static void update_ring_current(pv_t *pv) {
    double noise = (rand() / (double) RAND_MAX - 0.5) * 4.0;
    pv->value = 350.0 + noise;
    if (pv->value < 0) {
        pv->value = 0;
    }
    if (pv->value > 400) {
        pv->value = 400;
    }
}

static void update_vacuum(pv_t *pv) {
    // Log-scale: log10(pressure) with noise
    double log_p = -8.3 + ((rand() / (double) RAND_MAX - 0.5) * 0.2);
    pv->value = pow(10, log_p);
    // Clamp to range
    if (pv->value < 1e-10) {
        pv->value = 1e-10;
    }
    if (pv->value > 1e-8) {
        pv->value = 1e-8;
    }
}

static void update_temp(pv_t *pv) {
    // Slow drift
    static double drift = 0.0;
    drift += (rand() / (double) RAND_MAX - 0.5) * 0.01;
    pv->value = 23.0 + drift;
    // Clamp
    if (pv->value < 20) {
        pv->value = 20;
    }
    if (pv->value > 26) {
        pv->value = 26;
    }
}

static void update_detector_i0(pv_t *pv) {
    // Proportional to ring current
    pv_t *ring_current = pv_find("BL02:RING:CURRENT");
    if (!ring_current) {
        return;
    }

    double factor = ring_current->value / 350.0; // Normalize
    double base = 500000.0;
    double noise = (rand() / (double) RAND_MAX - 0.5) * 10000.0;
    pv->value = (base * factor) + noise;

    if (pv->value < 0) {
        pv->value = 0;
    }
    if (pv->value > 1e6) {
        pv->value = 1e6;
    }
}

static void update_detector_it(pv_t *pv) {
    // Similar to I0 but different base
    pv_t *ring_current = pv_find("BL02:RING:CURRENT");
    if (!ring_current) {
        return;
    }

    double factor = ring_current->value / 350.0;
    double base = 450000.0;
    double noise = (rand() / (double) RAND_MAX - 0.5) * 10000.0;
    pv->value = (base * factor) + noise;

    if (pv->value < 0) {
        pv->value = 0;
    }
    if (pv->value > 1e6) {
        pv->value = 1e6;
    }
}

static void update_detector_if(pv_t *pv) {
    // Fluorescence detector
    pv_t *ring_current = pv_find("BL02:RING:CURRENT");
    if (!ring_current) {
        return;
    }

    double factor = ring_current->value / 350.0;
    double base = 50000.0;
    double noise = (rand() / (double) RAND_MAX - 0.5) * 1000.0;
    pv->value = (base * factor) + noise;

    if (pv->value < 0) {
        pv->value = 0;
    }
    if (pv->value > 1e5) {
        pv->value = 1e5;
    }
}

static void update_shutter_status(pv_t *pv) {
    // Status follows command
    pv_t *cmd = pv_find("BL02:SHUTTER:CMD");
    if (cmd) {
        pv->value = cmd->value; // Simplified: instant response
    }
}

// Public functions
void devices_init(void) {
    g_pv_count = 0;
    g_motor_count = 0;

    // Register sensors (read-only)
    pv_register((pv_register_params_t) {.name = "BL02:RING:CURRENT",
                                        .type = PV_AI,
                                        .range = {0, 400},
                                        .writable = false,
                                        .update_fn = update_ring_current});
    pv_register((pv_register_params_t) {.name = "BL02:VACUUM:PRESSURE",
                                        .type = PV_AI,
                                        .range = {1e-10, 1e-8},
                                        .writable = false,
                                        .update_fn = update_vacuum});
    pv_register((pv_register_params_t) {.name = "BL02:HUTCH:TEMP",
                                        .type = PV_AI,
                                        .range = {20, 26},
                                        .writable = false,
                                        .update_fn = update_temp});
    pv_register((pv_register_params_t) {.name = "BL02:DET:I0",
                                        .type = PV_AI,
                                        .range = {0, 1e6},
                                        .writable = false,
                                        .update_fn = update_detector_i0});
    pv_register((pv_register_params_t) {.name = "BL02:DET:IT",
                                        .type = PV_AI,
                                        .range = {0, 1e6},
                                        .writable = false,
                                        .update_fn = update_detector_it});
    pv_register((pv_register_params_t) {.name = "BL02:DET:IF",
                                        .type = PV_AI,
                                        .range = {0, 1e5},
                                        .writable = false,
                                        .update_fn = update_detector_if});

    // Register shutter
    pv_register((pv_register_params_t) {.name = "BL02:SHUTTER:STATUS",
                                        .type = PV_BI,
                                        .range = {0, 1},
                                        .writable = false,
                                        .update_fn = update_shutter_status});
    pv_register((pv_register_params_t) {.name = "BL02:SHUTTER:CMD",
                                        .type = PV_BO,
                                        .range = {0, 1},
                                        .writable = true,
                                        .update_fn = NULL});

    // Register motors
    // Sample stage X
    motor_t *motor_x = &g_motors[g_motor_count++];
    motor_x->setpoint = pv_register((pv_register_params_t) {.name = "BL02:SAMPLE:X",
                                                            .type = PV_AO,
                                                            .range = {-10000, 10000},
                                                            .writable = true,
                                                            .update_fn = NULL});
    motor_x->readback = pv_register((pv_register_params_t) {.name = "BL02:SAMPLE:X.RBV",
                                                            .type = PV_AI,
                                                            .range = {-10000, 10000},
                                                            .writable = false,
                                                            .update_fn = NULL});
    motor_x->status_pv = pv_register((pv_register_params_t) {.name = "BL02:SAMPLE:X.DMOV",
                                                             .type = PV_BI,
                                                             .range = {0, 1},
                                                             .writable = false,
                                                             .update_fn = NULL});
    motor_x->velocity = 1000.0; // μm/s
    motor_x->accel = 0.0;       // Not used in linear interpolation
    motor_x->target = 0.0;
    motor_x->moving = false;

    // Sample stage Y
    motor_t *motor_y = &g_motors[g_motor_count++];
    motor_y->setpoint = pv_register((pv_register_params_t) {.name = "BL02:SAMPLE:Y",
                                                            .type = PV_AO,
                                                            .range = {-10000, 10000},
                                                            .writable = true,
                                                            .update_fn = NULL});
    motor_y->readback = pv_register((pv_register_params_t) {.name = "BL02:SAMPLE:Y.RBV",
                                                            .type = PV_AI,
                                                            .range = {-10000, 10000},
                                                            .writable = false,
                                                            .update_fn = NULL});
    motor_y->status_pv = pv_register((pv_register_params_t) {.name = "BL02:SAMPLE:Y.DMOV",
                                                             .type = PV_BI,
                                                             .range = {0, 1},
                                                             .writable = false,
                                                             .update_fn = NULL});
    motor_y->velocity = 1000.0;
    motor_y->accel = 0.0;
    motor_y->target = 0.0;
    motor_y->moving = false;

    // Sample stage Z
    motor_t *motor_z = &g_motors[g_motor_count++];
    motor_z->setpoint = pv_register((pv_register_params_t) {.name = "BL02:SAMPLE:Z",
                                                            .type = PV_AO,
                                                            .range = {-5000, 5000},
                                                            .writable = true,
                                                            .update_fn = NULL});
    motor_z->readback = pv_register((pv_register_params_t) {.name = "BL02:SAMPLE:Z.RBV",
                                                            .type = PV_AI,
                                                            .range = {-5000, 5000},
                                                            .writable = false,
                                                            .update_fn = NULL});
    motor_z->status_pv = pv_register((pv_register_params_t) {.name = "BL02:SAMPLE:Z.DMOV",
                                                             .type = PV_BI,
                                                             .range = {0, 1},
                                                             .writable = false,
                                                             .update_fn = NULL});
    motor_z->velocity = 1000.0;
    motor_z->accel = 0.0;
    motor_z->target = 0.0;
    motor_z->moving = false;

    // Sample stage THETA
    motor_t *motor_theta = &g_motors[g_motor_count++];
    motor_theta->setpoint = pv_register((pv_register_params_t) {.name = "BL02:SAMPLE:THETA",
                                                                .type = PV_AO,
                                                                .range = {-180, 180},
                                                                .writable = true,
                                                                .update_fn = NULL});
    motor_theta->readback = pv_register((pv_register_params_t) {.name = "BL02:SAMPLE:THETA.RBV",
                                                                .type = PV_AI,
                                                                .range = {-180, 180},
                                                                .writable = false,
                                                                .update_fn = NULL});
    motor_theta->status_pv = pv_register((pv_register_params_t) {.name = "BL02:SAMPLE:THETA.DMOV",
                                                                 .type = PV_BI,
                                                                 .range = {0, 1},
                                                                 .writable = false,
                                                                 .update_fn = NULL});
    motor_theta->velocity = 10.0; // deg/s
    motor_theta->accel = 0.0;
    motor_theta->target = 0.0;
    motor_theta->moving = false;

    // Monochromator energy
    motor_t *motor_energy = &g_motors[g_motor_count++];
    motor_energy->setpoint = pv_register((pv_register_params_t) {.name = "BL02:MONO:ENERGY",
                                                                 .type = PV_AO,
                                                                 .range = {4000, 20000},
                                                                 .writable = true,
                                                                 .update_fn = NULL});
    motor_energy->readback = pv_register((pv_register_params_t) {.name = "BL02:MONO:ENERGY.RBV",
                                                                 .type = PV_AI,
                                                                 .range = {4000, 20000},
                                                                 .writable = false,
                                                                 .update_fn = NULL});
    motor_energy->status_pv = pv_register((pv_register_params_t) {.name = "BL02:MONO:ENERGY.DMOV",
                                                                  .type = PV_BI,
                                                                  .range = {0, 1},
                                                                  .writable = false,
                                                                  .update_fn = NULL});
    motor_energy->velocity = 100.0; // eV/s
    motor_energy->accel = 0.0;
    motor_energy->target = 8000.0; // Default energy
    motor_energy->moving = false;
    motor_energy->readback->value = 8000.0; // Initialize readback

    // Initialize random seed
    srand((unsigned int) time(NULL));

    log_info("Initialized %d process variables, %d motors", g_pv_count, g_motor_count);
}

static void motor_update(motor_t *motor, double dt) {
    if (motor == NULL || !motor->moving) {
        return;
    }

    double current = motor->readback->value;
    double diff = motor->target - current;

    if (fabs(diff) < 0.001) {
        // Reached target
        motor->moving = false;
        motor->readback->value = motor->target;
        if (motor->status_pv) {
            motor->status_pv->value = 0.0; // IDLE
        }
        return;
    }

    // Linear interpolation (simplified)
    double rate = motor->velocity;
    double step = rate * dt;

    if (fabs(diff) < step) {
        motor->readback->value = motor->target;
        motor->moving = false;
        if (motor->status_pv) {
            motor->status_pv->value = 0.0;
        }
    } else {
        motor->readback->value += (diff > 0 ? step : -step);
        if (motor->status_pv) {
            motor->status_pv->value = 1.0; // MOVING
        }
    }
}

void devices_update(double dt) {
    // Update all PVs with update functions
    for (int i = 0; i < g_pv_count; i++) {
        if (g_pvs[i].update_fn != NULL) {
            g_pvs[i].update_fn(&g_pvs[i]);
        }
    }

    // Update motors
    for (int i = 0; i < g_motor_count; i++) {
        motor_update(&g_motors[i], dt);
    }
}

pv_t *pv_find(const char *name) {
    if (name == NULL) {
        return NULL;
    }

    for (int i = 0; i < g_pv_count; i++) {
        if (strcmp(g_pvs[i].name, name) == 0) {
            return &g_pvs[i];
        }
    }
    return NULL;
}

double pv_get(pv_t *pv) {
    if (pv == NULL) {
        return 0.0;
    }
    return pv->value;
}

bool pv_set(pv_t *pv, double value) {
    if (pv == NULL) {
        return false;
    }
    if (!pv->writable) {
        return false;
    }
    if (value < pv->min || value > pv->max) {
        return false;
    }

    pv->value = value;

    // For monochromator, update readback immediately (will be motor in Phase 2.2)
    if (strcmp(pv->name, "BL02:MONO:ENERGY") == 0) {
        pv_t *rbv = pv_find("BL02:MONO:ENERGY.RBV");
        if (rbv) {
            rbv->value = value;
        }
    }

    return true;
}

// Simple glob pattern matching: * matches any substring
static bool pattern_match(pattern_match_params_t params) {
    if (params.pattern == NULL || params.pattern[0] == '\0') {
        return true; // No pattern means match all
    }

    // Simple implementation: split pattern by * and check substrings
    const char *p = params.pattern;
    const char *s = params.str;

    while (*p != '\0') {
        if (*p == '*') {
            p++; // Skip *
            if (*p == '\0') {
                return true; // * at end matches rest
            }
            // Find next occurrence of pattern after *
            const char *next = strstr(s, p);
            if (next == NULL) {
                return false;
            }
            s = next;
        } else {
            if (*s != *p) {
                return false;
            }
            p++;
            s++;
        }
    }

    return *s == '\0'; // Must match entire string
}

int pv_list(const char *pattern, char *buf, size_t len) {
    if (buf == NULL || len == 0) {
        return 0;
    }

    buf[0] = '\0';
    int count = 0;
    size_t pos = 0;

    for (int i = 0; i < g_pv_count; i++) {
        const char *name = g_pvs[i].name;

        if (pattern_match((pattern_match_params_t) {.pattern = pattern, .str = name})) {
            size_t name_len = strlen(name);
            if (pos > 0) {
                if (pos + 1 < len) {
                    buf[pos++] = ',';
                } else {
                    break;
                }
            }
            if (pos + name_len < len) {
                strncpy(buf + pos, name, len - pos - 1);
                pos += name_len;
                buf[pos] = '\0';
                count++;
            } else {
                break;
            }
        }
    }

    return count;
}

motor_t *motor_find(const char *name) {
    if (name == NULL) {
        return NULL;
    }

    // Find motor by setpoint PV name
    for (int i = 0; i < g_motor_count; i++) {
        if (g_motors[i].setpoint && strcmp(g_motors[i].setpoint->name, name) == 0) {
            return &g_motors[i];
        }
    }
    return NULL;
}

bool motor_move(const char *motor_name, double target) {
    motor_t *motor = motor_find(motor_name);
    if (motor == NULL) {
        return false;
    }

    // Check limits
    if (motor->setpoint == NULL) {
        return false;
    }
    if (target < motor->setpoint->min || target > motor->setpoint->max) {
        return false;
    }

    motor->target = target;
    motor->setpoint->value = target;
    motor->moving = true;
    if (motor->status_pv) {
        motor->status_pv->value = 1.0; // MOVING
    }

    return true;
}

const char *motor_get_status_string(motor_t *motor) {
    if (motor == NULL) {
        return "UNKNOWN";
    }
    return (int) motor->moving ? "MOVING" : "IDLE";
}
