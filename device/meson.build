project(
    'beamline-sim',
    'c',
    version: '0.1.0',
    license: 'MIT',
    default_options: [
        'c_std=c23',
        'warning_level=3',
        'werror=true',
        'b_sanitize=address,undefined',
    ],
)

# Source files (to be populated in M2)
src_files = files(
    'src/main.c',
)

# Include directories
inc_dirs = include_directories('include')

# Main executable
executable(
    'beamline-sim',
    src_files,
    include_directories: inc_dirs,
    install: true,
)

# Tests (to be populated in M2)
# cmocka_dep = dependency('cmocka', required: false)
# if cmocka_dep.found()
#     subdir('tests')
# endif
