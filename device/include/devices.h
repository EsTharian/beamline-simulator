#ifndef BEAMLINE_DEVICES_H
#define BEAMLINE_DEVICES_H

#include <stdbool.h>
#include <stddef.h>
#include "config.h"

typedef enum {
    PV_AI,  // Analog Input
    PV_AO,  // Analog Output
    PV_BI,  // Binary Input
    PV_BO   // Binary Output
} pv_type_t;

typedef struct pv_t {
    char name[BEAMLINE_PV_NAME_MAX];
    pv_type_t type;
    double value;
    double min;
    double max;
    bool writable;
    void (*update_fn)(struct pv_t*);  // For simulation
} pv_t;

typedef struct {
    pv_t* setpoint;
    pv_t* readback;
    pv_t* status_pv;  // IDLE/MOVING as double
    double velocity;   // units/s
    double accel;      // units/s²
    double target;
    bool moving;
} motor_t;

// Named parameters struct for pv_register (C23 best practice)
typedef struct {
    const char *name;
    pv_type_t type;
    struct {
        double min;
        double max;
    } range;
    bool writable;
    void (*update_fn)(pv_t *);
} pv_register_params_t;

// Named parameters struct for pattern_match (C23 best practice)
typedef struct {
    const char *pattern;
    const char *str;
} pattern_match_params_t;

// Device management
void devices_init(void);
void devices_update(double dt);  // Called in main loop

// PV operations
pv_t* pv_find(const char* name);
double pv_get(pv_t* pv);
bool pv_set(pv_t* pv, double value);
int pv_list(const char* pattern, char* buf, size_t len);

// Motor operations
motor_t* motor_find(const char* name);
bool motor_move(const char* motor_name, double target);
const char* motor_get_status_string(motor_t* motor);

#endif // BEAMLINE_DEVICES_H
