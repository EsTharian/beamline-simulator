#include <stdarg.h>
#include <stddef.h>
#include <setjmp.h>
#include <string.h>

#include <cmocka.h>

#include "protocol.h"

static void test_parse_get(void** state) {
    (void)state;
    cmd_t cmd;
    assert_true(protocol_parse("GET:BL02:RING:CURRENT\n", &cmd));
    assert_int_equal(cmd.type, CMD_GET);
    assert_string_equal(cmd.target, "BL02:RING:CURRENT");
    assert_false(cmd.has_value);
}

static void test_parse_put(void** state) {
    (void)state;
    cmd_t cmd;
    assert_true(protocol_parse("PUT:BL02:MONO:ENERGY:7112\n", &cmd));
    assert_int_equal(cmd.type, CMD_PUT);
    assert_string_equal(cmd.target, "BL02:MONO:ENERGY");
    assert_true(cmd.has_value);
    assert_double_equal(cmd.value, 7112.0, 0.001);
}

static void test_parse_ping(void** state) {
    (void)state;
    cmd_t cmd;
    assert_true(protocol_parse("PING\n", &cmd));
    assert_int_equal(cmd.type, CMD_PING);
}

static void test_parse_quit(void** state) {
    (void)state;
    cmd_t cmd;
    assert_true(protocol_parse("QUIT\n", &cmd));
    assert_int_equal(cmd.type, CMD_QUIT);
}

static void test_parse_move(void** state) {
    (void)state;
    cmd_t cmd;
    assert_true(protocol_parse("MOVE:BL02:SAMPLE:X:1000\n", &cmd));
    assert_int_equal(cmd.type, CMD_MOVE);
    assert_string_equal(cmd.target, "BL02:SAMPLE:X");
    assert_true(cmd.has_value);
    assert_double_equal(cmd.value, 1000.0, 0.001);
}

static void test_parse_status(void** state) {
    (void)state;
    cmd_t cmd;
    assert_true(protocol_parse("STATUS:BL02:SAMPLE:X\n", &cmd));
    assert_int_equal(cmd.type, CMD_STATUS);
    assert_string_equal(cmd.target, "BL02:SAMPLE:X");
}

static void test_parse_monitor(void** state) {
    (void)state;
    cmd_t cmd;
    assert_true(protocol_parse("MONITOR:BL02:DET:I0:100\n", &cmd));
    assert_int_equal(cmd.type, CMD_MONITOR);
    assert_string_equal(cmd.target, "BL02:DET:I0");
    assert_int_equal(cmd.monitor_interval_ms, 100);
}

static void test_format_response(void** state) {
    (void)state;
    char buf[256];
    protocol_format_response((protocol_format_response_params_t){.buf = buf, .len = sizeof(buf), .status = "OK", .data = "350.5"});
    assert_string_equal(buf, "OK:350.5\n");
}

static void test_format_error(void** state) {
    (void)state;
    char buf[256];
    protocol_format_error((protocol_format_error_params_t){.buf = buf, .len = sizeof(buf), .err_code = ERR_UNKNOWN_PV});
    assert_string_equal(buf, "ERR:UNKNOWN_PV\n");
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_parse_get),
        cmocka_unit_test(test_parse_put),
        cmocka_unit_test(test_parse_ping),
        cmocka_unit_test(test_parse_quit),
        cmocka_unit_test(test_parse_move),
        cmocka_unit_test(test_parse_status),
        cmocka_unit_test(test_parse_monitor),
        cmocka_unit_test(test_format_response),
        cmocka_unit_test(test_format_error),
    };

    return cmocka_run_group_tests(tests, NULL, NULL);
}
