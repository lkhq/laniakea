# Meson definition for Laniakea System and Integration tests

#
# Code Linters
#
if get_option('linting')
    pylint_paths = [
        join_paths(source_root, 'src'),
        join_paths(source_root, 'tests'),
       # join_paths(source_root, 'contrib')
    ]

    flake8_exe = find_program('flake8')
    test('flake8',
        flake8_exe,
        args: ['--show-source',
               '--statistics',
               source_root],
        workdir: source_root,
        suite: 'linters',
        timeout: 180,
    )

    pylint_exe = find_program('pylint')
    test('pylint',
        py,
        args: [pylint_exe.path(),
               '-f', 'colorized',
               pylint_paths],
        workdir: source_root,
        suite: 'linters',
        timeout: 180,
    )

    mypy_exe = find_program('mypy')
    test('mypy',
        py,
        args: [mypy_exe.path(),
               join_paths(source_root, 'src'),
               '--exclude', 'src\/(web|webswview)\/(manage|wsgi)\.py$'
               ],
        workdir: source_root,
        suite: 'linters',
        timeout: 180,
    )
endif

py_exe = find_program('python3')
test('pytest',
    py_exe,
    args: ['-m', 'pytest'],
    workdir: source_root,
    is_parallel: false,
    suite: 'integration',
    timeout: 420,
)
