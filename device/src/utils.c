#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif

#include "utils.h"

#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

// Logging implementation
void log_init(void) {
    // Using stderr for logging (can be changed to syslog later)
}

void log_info(const char* fmt, ...) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    struct tm* tm_info = localtime(&ts.tv_sec);

    fprintf(stderr, "[%04d-%02d-%02d %02d:%02d:%02d] INFO: ",
            tm_info->tm_year + 1900, tm_info->tm_mon + 1, tm_info->tm_mday,
            tm_info->tm_hour, tm_info->tm_min, tm_info->tm_sec);

    va_list args;
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);
    fprintf(stderr, "\n");
}

void log_warn(const char* fmt, ...) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    struct tm* tm_info = localtime(&ts.tv_sec);

    fprintf(stderr, "[%04d-%02d-%02d %02d:%02d:%02d] WARN: ",
            tm_info->tm_year + 1900, tm_info->tm_mon + 1, tm_info->tm_mday,
            tm_info->tm_hour, tm_info->tm_min, tm_info->tm_sec);

    va_list args;
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);
    fprintf(stderr, "\n");
}

void log_error(const char* fmt, ...) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    struct tm* tm_info = localtime(&ts.tv_sec);

    fprintf(stderr, "[%04d-%02d-%02d %02d:%02d:%02d] ERROR: ",
            tm_info->tm_year + 1900, tm_info->tm_mon + 1, tm_info->tm_mday,
            tm_info->tm_hour, tm_info->tm_min, tm_info->tm_sec);

    va_list args;
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);
    fprintf(stderr, "\n");
}

void log_debug(const char* fmt, ...) {
    // Debug logging (can be enabled via compile flag)
    (void)fmt;
}

// Memory safety
void* safe_malloc(size_t size) {
    void* ptr = malloc(size);
    if (ptr == NULL) {
        log_error("malloc(%zu) failed: %s", size, strerror(errno));
        exit(EXIT_FAILURE);
    }
    return ptr;
}

void* safe_realloc(void* ptr, size_t size) {
    void* new_ptr = realloc(ptr, size);
    if (new_ptr == NULL && size > 0) {
        log_error("realloc(%zu) failed: %s", size, strerror(errno));
        exit(EXIT_FAILURE);
    }
    return new_ptr;
}

// String utilities
void trim(char* str) {
    if (str == NULL) {
        return;
    }

    // Trim leading whitespace
    char* start = str;
    while (*start == ' ' || *start == '\t' || *start == '\n' || *start == '\r') {
        start++;
    }

    // Trim trailing whitespace
    char* end = start + strlen(start) - 1;
    while (end > start && (*end == ' ' || *end == '\t' || *end == '\n' || *end == '\r')) {
        *end = '\0';
        end--;
    }

    // Move trimmed string to start
    if (start != str) {
        size_t len = strlen(start) + 1;
        memmove(str, start, len);
    }
}

bool str_to_double(const char* str, double* out) {
    if (str == NULL || out == NULL) {
        return false;
    }

    char* endptr;
    errno = 0;
    double val = strtod(str, &endptr);

    // Check for conversion errors
    if (errno == ERANGE) {
        return false;  // Overflow or underflow
    }
    if (endptr == str) {
        return false;  // No conversion performed
    }
    if (*endptr != '\0' && *endptr != '\n' && *endptr != '\r') {
        // Check if remaining characters are just whitespace
        while (*endptr == ' ' || *endptr == '\t') {
            endptr++;
        }
        if (*endptr != '\0' && *endptr != '\n' && *endptr != '\r') {
            return false;  // Invalid characters
        }
    }

    *out = val;
    return true;
}
