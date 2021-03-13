# Meson definition for Laniakea System and Integration tests

#
# Code Linters
#
if get_option('linting')
    flake8_exe = find_program('flake8')
    test('flake8',
        flake8_exe,
        args: ['--show-source',
               '--statistics',
               source_root],
        suite: 'linters'
    )
endif

py_exe = find_program('python3')
test('pytest',
    py_exe,
    args: ['-m', 'pytest'],
    workdir: source_root,
    is_parallel: false,
    suite: 'pytest'
)
