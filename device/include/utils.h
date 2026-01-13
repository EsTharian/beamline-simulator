#ifndef BEAMLINE_UTILS_H
#define BEAMLINE_UTILS_H

#include <stdbool.h>
#include <stddef.h>

// Logging
void log_init(void);
void log_info(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
void log_warn(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
void log_error(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
void log_debug(const char *fmt, ...);

// Memory safety
void *safe_malloc(size_t size);
void *safe_realloc(void *ptr, size_t size);

// String utilities
void trim(char *str);
bool str_to_double(const char *str, double *out);

#endif // BEAMLINE_UTILS_H
