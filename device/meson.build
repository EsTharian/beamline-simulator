project(
    'beamline-sim',
    'c',
    version: '0.1.0',
    license: 'MIT',
    default_options: [
        'c_std=c2x',
        'warning_level=3',
        'werror=true',
        'b_sanitize=address,undefined',
    ],
)

# Source files
src_files = files(
    'src/main.c',
    'src/utils.c',
    'src/devices.c',
    'src/protocol.c',
    'src/server.c',
)

# Include directories
inc_dirs = include_directories('include')

# Math library dependency
cc = meson.get_compiler('c')
math_dep = cc.find_library('m', required: true)

# Main executable
executable(
    'beamline-sim',
    src_files,
    include_directories: inc_dirs,
    dependencies: math_dep,
    install: true,
)

# Tests
cmocka_dep = dependency('cmocka', required: true)
if cmocka_dep.found()
    test_protocol = executable(
        'test_protocol',
        'tests/test_protocol.c',
        'src/protocol.c',
        'src/utils.c',
        include_directories: inc_dirs,
        dependencies: [cmocka_dep],
        c_args: ['-DHAVE_CMOCKA'],
    )
    test('protocol', test_protocol)

    test_devices = executable(
        'test_devices',
        'tests/test_devices.c',
        'src/devices.c',
        'src/utils.c',
        include_directories: inc_dirs,
        dependencies: [cmocka_dep, math_dep],
        c_args: ['-DHAVE_CMOCKA'],
    )
    test('devices', test_devices)
endif
