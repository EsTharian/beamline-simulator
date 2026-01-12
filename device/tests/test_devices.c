#include <setjmp.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>

#include <cmocka.h>

#include "devices.h"

static void test_pv_find(void **state) {
    (void) state;
    devices_init();
    pv_t *pv = pv_find("BL02:RING:CURRENT");
    assert_non_null(pv);
    assert_string_equal(pv->name, "BL02:RING:CURRENT");
}

static void test_pv_get_set(void **state) {
    (void) state;
    devices_init();
    pv_t *pv = pv_find("BL02:MONO:ENERGY");
    assert_non_null(pv);
    assert_true(pv_set(pv, 8000.0));
    assert_double_equal(pv_get(pv), 8000.0, 0.001);
}

static void test_pv_set_invalid_range(void **state) {
    (void) state;
    devices_init();
    pv_t *pv = pv_find("BL02:MONO:ENERGY");
    assert_non_null(pv);
    assert_false(pv_set(pv, 50000.0)); // Out of range
}

static void test_pv_set_readonly(void **state) {
    (void) state;
    devices_init();
    pv_t *pv = pv_find("BL02:RING:CURRENT");
    assert_non_null(pv);
    assert_false(pv_set(pv, 100.0)); // Read-only
}

static void test_motor_find(void **state) {
    (void) state;
    devices_init();
    motor_t *motor = motor_find("BL02:SAMPLE:X");
    assert_non_null(motor);
    assert_non_null(motor->setpoint);
    assert_non_null(motor->readback);
}

static void test_motor_move(void **state) {
    (void) state;
    devices_init();
    assert_true(motor_move("BL02:SAMPLE:X", 1000.0));
    motor_t *motor = motor_find("BL02:SAMPLE:X");
    assert_non_null(motor);
    assert_true(motor->moving);
    assert_double_equal(motor->target, 1000.0, 0.001);
}

static void test_motor_status(void **state) {
    (void) state;
    devices_init();
    motor_t *motor = motor_find("BL02:SAMPLE:X");
    assert_non_null(motor);
    const char *status = motor_get_status_string(motor);
    assert_string_equal(status, "IDLE");
}

int main(void) {
    const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_pv_find),
        cmocka_unit_test(test_pv_get_set),
        cmocka_unit_test(test_pv_set_invalid_range),
        cmocka_unit_test(test_pv_set_readonly),
        cmocka_unit_test(test_motor_find),
        cmocka_unit_test(test_motor_move),
        cmocka_unit_test(test_motor_status),
    };

    return cmocka_run_group_tests(tests, NULL, NULL);
}
