# Meson definition for Laniakea System and Integration tests

#
# Code Linters
#
if get_option('linting')
    pylint_paths = [
        join_paths(source_root, 'src'),
        join_paths(source_root, 'tests'),
        join_paths(source_root, 'docs'),
        join_paths(source_root, 'contrib')
    ]

    flake8_exe = find_program('flake8')
    test('flake8',
        flake8_exe,
        args: ['--show-source',
               '--statistics',
               pylint_paths],
        workdir: source_root,
        suite: 'linters'
    )

    pylint_exe = find_program('pylint')
    test('pylint',
        pylint_exe,
        args: ['-f', 'colorized',
               pylint_paths],
        workdir: source_root,
        suite: 'linters'
    )
endif

py_exe = find_program('python3')
test('pytest',
    py_exe,
    args: ['-m', 'pytest'],
    workdir: source_root,
    is_parallel: false,
    suite: 'integration'
)
