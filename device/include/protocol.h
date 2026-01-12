#ifndef BEAMLINE_PROTOCOL_H
#define BEAMLINE_PROTOCOL_H

#include <stdbool.h>
#include <stddef.h>
#include "config.h"

typedef enum {
    CMD_GET,
    CMD_PUT,
    CMD_MOVE,
    CMD_STATUS,
    CMD_LIST,
    CMD_MONITOR,
    CMD_STOP,
    CMD_PING,
    CMD_QUIT,
    CMD_INVALID
} cmd_type_t;

typedef enum {
    ERR_UNKNOWN_CMD,
    ERR_UNKNOWN_PV,
    ERR_INVALID_VALUE,
    ERR_MOTOR_FAULT,
    ERR_INTERNAL
} error_code_t;

typedef struct {
    cmd_type_t type;
    char target[BEAMLINE_PV_NAME_MAX];
    double value;
    bool has_value;
    int monitor_interval_ms;  // For MONITOR command
} cmd_t;

// Command parsing
bool protocol_parse(const char* input, cmd_t* cmd);

// Named parameters struct for protocol_format_error
typedef struct {
    char *buf;
    size_t len;
    error_code_t err_code;
} protocol_format_error_params_t;

// Named parameters struct for protocol_format_response
typedef struct {
    char *buf;
    size_t len;
    const char *status;
    const char *data;
} protocol_format_response_params_t;

// Response formatting
void protocol_format_response(protocol_format_response_params_t params);
void protocol_format_error(protocol_format_error_params_t params);
const char* error_code_string(error_code_t code);

#endif // BEAMLINE_PROTOCOL_H
