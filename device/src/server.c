#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif

#include "server.h"

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#include <arpa/inet.h>
#include <netinet/in.h>

#include "config.h"
#include "devices.h"
#include "protocol.h"
#include "utils.h"

typedef struct {
    int fd;
    bool active;
    char recv_buf[BEAMLINE_CMD_BUFFER_SIZE];
    size_t recv_len;
    bool monitoring;
    char monitor_pv[BEAMLINE_PV_NAME_MAX];
    int monitor_interval_ms;
    int64_t last_monitor_time;
} client_t;

static client_t g_clients[BEAMLINE_MAX_CLIENTS];
static int g_client_count = 0;
static int g_listen_fd = -1;

static int64_t get_time_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ((int64_t) ts.tv_sec * 1000) + ((int64_t) ts.tv_nsec / 1000000);
}

static void client_disconnect(client_t *client) {
    if (client == NULL || !client->active) {
        return;
    }

    log_info("Client disconnected (fd=%d)", client->fd);
    close(client->fd);
    client->active = false;
    client->monitoring = false;
    client->recv_len = 0;
    g_client_count--;
}

// Helper: Execute a parsed command and send response
static void execute_command(client_t *client, const cmd_t *cmd) {
    char response[BEAMLINE_RESPONSE_BUFFER_SIZE];

    switch (cmd->type) {
    case CMD_GET: {
        pv_t *pv = pv_find(cmd->target);
        if (pv == NULL) {
            protocol_format_error((protocol_format_error_params_t) {
                .buf = response, .len = sizeof(response), .err_code = ERR_UNKNOWN_PV});
        } else {
            char value_str[64];
            snprintf(value_str, sizeof(value_str), "%.6g", pv_get(pv));
            protocol_format_response((protocol_format_response_params_t) {
                .buf = response, .len = sizeof(response), .status = "OK", .data = value_str});
        }
        send(client->fd, response, strlen(response), 0);
        break;
    }

    case CMD_PUT: {
        pv_t *pv = pv_find(cmd->target);
        if (pv == NULL) {
            protocol_format_error((protocol_format_error_params_t) {
                .buf = response, .len = sizeof(response), .err_code = ERR_UNKNOWN_PV});
        } else if (!pv_set(pv, cmd->value)) {
            protocol_format_error((protocol_format_error_params_t) {
                .buf = response, .len = sizeof(response), .err_code = ERR_INVALID_VALUE});
        } else {
            protocol_format_response((protocol_format_response_params_t) {
                .buf = response, .len = sizeof(response), .status = "OK", .data = "PUT"});
        }
        send(client->fd, response, strlen(response), 0);
        break;
    }

    case CMD_PING:
        protocol_format_response((protocol_format_response_params_t) {
            .buf = response, .len = sizeof(response), .status = "OK", .data = "PONG"});
        send(client->fd, response, strlen(response), 0);
        break;

    case CMD_QUIT:
        protocol_format_response((protocol_format_response_params_t) {
            .buf = response, .len = sizeof(response), .status = "OK", .data = "BYE"});
        send(client->fd, response, strlen(response), 0);
        client_disconnect(client);
        return;

    case CMD_MONITOR:
        client->monitoring = true;
        strncpy(client->monitor_pv, cmd->target, BEAMLINE_PV_NAME_MAX - 1);
        client->monitor_pv[BEAMLINE_PV_NAME_MAX - 1] = '\0';
        client->monitor_interval_ms = cmd->monitor_interval_ms;
        client->last_monitor_time = get_time_ms();
        protocol_format_response((protocol_format_response_params_t) {
            .buf = response, .len = sizeof(response), .status = "OK", .data = "MONITORING"});
        send(client->fd, response, strlen(response), 0);
        break;

    case CMD_STOP:
        client->monitoring = false;
        protocol_format_response((protocol_format_response_params_t) {
            .buf = response, .len = sizeof(response), .status = "OK", .data = "STOPPED"});
        send(client->fd, response, strlen(response), 0);
        break;

    case CMD_LIST: {
        char list_buf[BEAMLINE_RESPONSE_BUFFER_SIZE];
        int count =
            pv_list(cmd->target[0] != '\0' ? cmd->target : NULL, list_buf, sizeof(list_buf));
        if (count > 0) {
            protocol_format_response((protocol_format_response_params_t) {
                .buf = response, .len = sizeof(response), .status = "OK", .data = list_buf});
        } else {
            protocol_format_response((protocol_format_response_params_t) {
                .buf = response, .len = sizeof(response), .status = "OK", .data = ""});
        }
        send(client->fd, response, strlen(response), 0);
        break;
    }

    case CMD_MOVE: {
        if (!motor_move(cmd->target, cmd->value)) {
            protocol_format_error((protocol_format_error_params_t) {
                .buf = response, .len = sizeof(response), .err_code = ERR_INVALID_VALUE});
        } else {
            protocol_format_response((protocol_format_response_params_t) {
                .buf = response, .len = sizeof(response), .status = "OK", .data = "MOVING"});
        }
        send(client->fd, response, strlen(response), 0);
        break;
    }

    case CMD_STATUS: {
        motor_t *motor = motor_find(cmd->target);
        if (motor == NULL) {
            protocol_format_error((protocol_format_error_params_t) {
                .buf = response, .len = sizeof(response), .err_code = ERR_UNKNOWN_PV});
        } else {
            const char *status_str = motor_get_status_string(motor);
            protocol_format_response((protocol_format_response_params_t) {
                .buf = response, .len = sizeof(response), .status = "OK", .data = status_str});
        }
        send(client->fd, response, strlen(response), 0);
        break;
    }

    default:
        protocol_format_error((protocol_format_error_params_t) {
            .buf = response, .len = sizeof(response), .err_code = ERR_UNKNOWN_CMD});
        send(client->fd, response, strlen(response), 0);
        break;
    }
}

static void client_handle(client_t *client) {
    if (client == NULL || !client->active) {
        return;
    }

    // Read data
    ssize_t n = recv(client->fd, client->recv_buf + client->recv_len,
                     BEAMLINE_CMD_BUFFER_SIZE - client->recv_len - 1, MSG_DONTWAIT);

    if (n < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) {
            // No data available, return (monitoring handled separately)
            return;
        }
        log_error("recv() failed: %s", strerror(errno));
        client_disconnect(client);
        return;
    }

    if (n == 0) {
        // Connection closed
        client_disconnect(client);
        return;
    }

    if (n > 0) {
        client->recv_len += (size_t) n;
        client->recv_buf[client->recv_len] = '\0';
    }

    // Process complete lines
    char *line_start = client->recv_buf;
    while (true) {
        char *newline = strchr(line_start, '\n');
        if (newline == NULL) {
            break;
        }

        *newline = '\0';
        cmd_t cmd;
        if (protocol_parse(line_start, &cmd)) {
            execute_command(client, &cmd);
        } else {
            char response[BEAMLINE_RESPONSE_BUFFER_SIZE];
            protocol_format_error((protocol_format_error_params_t) {
                .buf = response, .len = sizeof(response), .err_code = ERR_UNKNOWN_CMD});
            send(client->fd, response, strlen(response), 0);
        }

        // Move remaining data to start
        size_t remaining = client->recv_len - (newline - client->recv_buf) - 1;
        if (remaining > 0) {
            memmove(client->recv_buf, newline + 1, remaining);
        }
        client->recv_len = remaining;
        line_start = client->recv_buf;
    }
}

static void client_accept(int listen_fd) {
    struct sockaddr_in client_addr;
    socklen_t addr_len = sizeof(client_addr);

    int client_fd = accept(listen_fd, (struct sockaddr *) &client_addr, &addr_len);
    if (client_fd < 0) {
        if (errno != EAGAIN && errno != EWOULDBLOCK) {
            log_error("accept() failed: %s", strerror(errno));
        }
        return;
    }

    // Find free slot
    int slot = -1;
    for (int i = 0; i < BEAMLINE_MAX_CLIENTS; i++) {
        if (!g_clients[i].active) {
            slot = i;
            break;
        }
    }

    if (slot < 0) {
        log_warn("Max clients reached, rejecting connection");
        close(client_fd);
        return;
    }

    // Initialize client
    client_t *client = &g_clients[slot];
    client->fd = client_fd;
    client->active = true;
    client->recv_len = 0;
    client->monitoring = false;
    client->monitor_pv[0] = '\0';
    client->monitor_interval_ms = 0;
    client->last_monitor_time = 0;
    g_client_count++;

    log_info("Client connected (fd=%d, addr=%s)", client_fd, inet_ntoa(client_addr.sin_addr));
}

int server_init(void) {
    g_listen_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (g_listen_fd < 0) {
        log_error("socket() failed: %s", strerror(errno));
        return -1;
    }

    // Set SO_REUSEADDR
    int opt = 1;
    if (setsockopt(g_listen_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        log_error("setsockopt() failed: %s", strerror(errno));
        close(g_listen_fd);
        return -1;
    }

    // Bind
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(BEAMLINE_PORT);

    if (bind(g_listen_fd, (struct sockaddr *) &addr, sizeof(addr)) < 0) {
        log_error("bind() failed: %s", strerror(errno));
        close(g_listen_fd);
        return -1;
    }

    // Listen
    if (listen(g_listen_fd, BEAMLINE_BACKLOG) < 0) {
        log_error("listen() failed: %s", strerror(errno));
        close(g_listen_fd);
        return -1;
    }

    // Initialize client array
    for (int i = 0; i < BEAMLINE_MAX_CLIENTS; i++) {
        g_clients[i].active = false;
    }
    g_client_count = 0;

    return g_listen_fd;
}

// Helper: Setup select() file descriptor set
static void setup_select_fds(int listen_fd, fd_set *read_fds, int *max_fd) {
    FD_ZERO(read_fds);
    FD_SET(listen_fd, read_fds);
    *max_fd = listen_fd;

    // Add all client FDs
    for (int i = 0; i < BEAMLINE_MAX_CLIENTS; i++) {
        if (g_clients[i].active) {
            FD_SET(g_clients[i].fd, read_fds);
            if (g_clients[i].fd > *max_fd) {
                *max_fd = g_clients[i].fd;
            }
        }
    }
}

// Helper: Check and send monitoring updates
static void check_monitoring(void) {
    for (int i = 0; i < BEAMLINE_MAX_CLIENTS; i++) {
        if ((int) g_clients[i].active && (int) g_clients[i].monitoring) {
            int64_t now = get_time_ms();
            if (now - g_clients[i].last_monitor_time >= g_clients[i].monitor_interval_ms) {
                pv_t *pv = pv_find(g_clients[i].monitor_pv);
                if (pv != NULL) {
                    char data_msg[BEAMLINE_RESPONSE_BUFFER_SIZE];
                    char value_str[64];
                    snprintf(value_str, sizeof(value_str), "%.6g", pv_get(pv));
                    snprintf(data_msg, sizeof(data_msg), "DATA:%s\n", value_str);
                    send(g_clients[i].fd, data_msg, strlen(data_msg), 0);
                }
                g_clients[i].last_monitor_time = now;
            }
        }
    }
}

void server_run_once(int listen_fd) {
    fd_set read_fds;
    int max_fd;
    setup_select_fds(listen_fd, &read_fds, &max_fd);

    struct timeval timeout = {
        .tv_sec = 0,
        .tv_usec = (long) BEAMLINE_SELECT_TIMEOUT_MS * 1000L,
    };

    int nready = select(max_fd + 1, &read_fds, NULL, NULL, &timeout);
    if (nready < 0) {
        if (errno != EINTR) {
            log_error("select() failed: %s", strerror(errno));
        }
        return;
    }

    // Check for new connection
    if (FD_ISSET(listen_fd, &read_fds)) {
        client_accept(listen_fd);
    }

    // Handle client data (only for FDs that are ready)
    for (int i = 0; i < BEAMLINE_MAX_CLIENTS; i++) {
        if ((int) g_clients[i].active && FD_ISSET(g_clients[i].fd, &read_fds)) {
            client_handle(&g_clients[i]);
        }
    }

    // Check monitoring for all active clients
    check_monitoring();
}

void server_cleanup(int listen_fd) {
    // Disconnect all clients
    for (int i = 0; i < BEAMLINE_MAX_CLIENTS; i++) {
        if (g_clients[i].active) {
            client_disconnect(&g_clients[i]);
        }
    }

    if (listen_fd >= 0) {
        close(listen_fd);
    }
}
