#include "protocol.h"

#include <stdio.h>
#include <string.h>

#include "utils.h"

const char *error_code_string(error_code_t code) {
    switch (code) {
    case ERR_UNKNOWN_CMD:
        return "UNKNOWN_CMD";
    case ERR_UNKNOWN_PV:
        return "UNKNOWN_PV";
    case ERR_INVALID_VALUE:
        return "INVALID_VALUE";
    case ERR_MOTOR_FAULT:
        return "MOTOR_FAULT";
    case ERR_INTERNAL:
        return "INTERNAL";
    default:
        return "UNKNOWN";
    }
}

// Helper: Parse simple commands without colon (PING, QUIT, STOP, LIST)
static bool parse_simple_command(const char *cmd_str, cmd_t *cmd) {
    if (strcmp(cmd_str, "PING") == 0) {
        cmd->type = CMD_PING;
        return true;
    }
    if (strcmp(cmd_str, "QUIT") == 0) {
        cmd->type = CMD_QUIT;
        return true;
    }
    if (strcmp(cmd_str, "STOP") == 0) {
        cmd->type = CMD_STOP;
        return true;
    }
    if (strcmp(cmd_str, "LIST") == 0) {
        cmd->type = CMD_LIST;
        return true;
    }
    return false;
}

// Helper: Parse PUT command (PUT:PV:VALUE)
static bool parse_put_command(const char *target_str, cmd_t *cmd) {
    char *value_colon = strrchr((char *) target_str, ':');
    if (value_colon == NULL) {
        return false;
    }
    *value_colon = '\0';
    const char *pv_name = target_str;
    const char *value_str = value_colon + 1;

    if (!str_to_double(value_str, &cmd->value)) {
        return false;
    }

    cmd->type = CMD_PUT;
    strncpy(cmd->target, pv_name, BEAMLINE_PV_NAME_MAX - 1);
    cmd->target[BEAMLINE_PV_NAME_MAX - 1] = '\0';
    cmd->has_value = true;
    return true;
}

// Helper: Parse MOVE command (MOVE:MOTOR:POSITION)
static bool parse_move_command(const char *target_str, cmd_t *cmd) {
    char *value_colon = strrchr((char *) target_str, ':');
    if (value_colon == NULL) {
        return false;
    }
    *value_colon = '\0';
    const char *motor_name = target_str;
    const char *pos_str = value_colon + 1;

    if (!str_to_double(pos_str, &cmd->value)) {
        return false;
    }

    cmd->type = CMD_MOVE;
    strncpy(cmd->target, motor_name, BEAMLINE_PV_NAME_MAX - 1);
    cmd->target[BEAMLINE_PV_NAME_MAX - 1] = '\0';
    cmd->has_value = true;
    return true;
}

// Helper: Parse MONITOR command (MONITOR:PV:INTERVAL_MS)
static bool parse_monitor_command(const char *target_str, cmd_t *cmd) {
    char *interval_colon = strrchr((char *) target_str, ':');
    if (interval_colon == NULL) {
        return false;
    }
    *interval_colon = '\0';
    const char *pv_name = target_str;
    const char *interval_str = interval_colon + 1;

    double interval_d;
    if (!str_to_double(interval_str, &interval_d)) {
        return false;
    }

    cmd->type = CMD_MONITOR;
    strncpy(cmd->target, pv_name, BEAMLINE_PV_NAME_MAX - 1);
    cmd->target[BEAMLINE_PV_NAME_MAX - 1] = '\0';
    cmd->monitor_interval_ms = (int) interval_d;
    return true;
}

bool protocol_parse(const char *input, cmd_t *cmd) {
    if (input == NULL || cmd == NULL) {
        return false;
    }

    // Initialize cmd
    cmd->type = CMD_INVALID;
    cmd->target[0] = '\0';
    cmd->value = 0.0;
    cmd->has_value = false;
    cmd->monitor_interval_ms = 0;

    // Copy input to work buffer and trim
    char work[BEAMLINE_CMD_BUFFER_SIZE];
    strncpy(work, input, sizeof(work) - 1);
    work[sizeof(work) - 1] = '\0';
    trim(work);

    // Remove trailing newline if present
    size_t len = strlen(work);
    if (len > 0 && work[len - 1] == '\n') {
        work[len - 1] = '\0';
        len--;
    }

    if (len == 0) {
        return false;
    }

    // Find first colon
    char *colon = strchr(work, ':');
    if (colon == NULL) {
        // Commands without colon: PING, QUIT, STOP, LIST
        return parse_simple_command(work, cmd);
    }

    // Split command and target
    *colon = '\0';
    const char *cmd_str = work;
    const char *target_str = colon + 1;

    // Parse command type
    if (strcmp(cmd_str, "GET") == 0) {
        cmd->type = CMD_GET;
        strncpy(cmd->target, target_str, BEAMLINE_PV_NAME_MAX - 1);
        cmd->target[BEAMLINE_PV_NAME_MAX - 1] = '\0';
        return true;
    }

    if (strcmp(cmd_str, "PUT") == 0) {
        return parse_put_command(target_str, cmd);
    }

    if (strcmp(cmd_str, "MOVE") == 0) {
        return parse_move_command(target_str, cmd);
    }

    if (strcmp(cmd_str, "STATUS") == 0) {
        cmd->type = CMD_STATUS;
        strncpy(cmd->target, target_str, BEAMLINE_PV_NAME_MAX - 1);
        cmd->target[BEAMLINE_PV_NAME_MAX - 1] = '\0';
        return true;
    }

    if (strcmp(cmd_str, "LIST") == 0) {
        cmd->type = CMD_LIST;
        if (target_str[0] != '\0') {
            strncpy(cmd->target, target_str, BEAMLINE_PV_NAME_MAX - 1);
            cmd->target[BEAMLINE_PV_NAME_MAX - 1] = '\0';
        }
        return true;
    }

    if (strcmp(cmd_str, "MONITOR") == 0) {
        return parse_monitor_command(target_str, cmd);
    }

    return false;
}

void protocol_format_response(protocol_format_response_params_t params) {
    if (params.buf == NULL || params.len == 0) {
        return;
    }

    if (params.data != NULL && params.data[0] != '\0') {
        snprintf(params.buf, params.len, "%s:%s\n", params.status, params.data);
    } else {
        snprintf(params.buf, params.len, "%s\n", params.status);
    }
}

void protocol_format_error(protocol_format_error_params_t params) {
    if (params.buf == NULL || params.len == 0) {
        return;
    }

    const char *err_str = error_code_string(params.err_code);
    snprintf(params.buf, params.len, "ERR:%s\n", err_str);
}
