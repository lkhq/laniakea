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
        args: [pylint_exe.full_path(),
               '-f', 'colorized',
               pylint_paths],
        workdir: source_root,
        suite: 'linters',
        timeout: 180,
    )

    mypy_exe = find_program('mypy')
    mypy_typeinst_args = []
    if get_option('mypy-install-types')
        mypy_typeinst_args = ['--install-types', '--non-interactive']
    endif
    test('mypy',
        py,
        args: [mypy_exe.full_path(),
               mypy_typeinst_args,
               join_paths(source_root, 'src'),
               '--exclude', 'src/(webdash|webswview|webupload)/(manage|wsgi)\\.py$|src/laniakea/alembic/env\\.py$',
               ],
        workdir: source_root,
        suite: 'linters',
        timeout: 180,
    )

    isort_exe = find_program('isort')
    test('isort',
        py,
        args: [isort_exe.full_path(),
               '--diff', '.'],
        workdir: source_root,
        suite: 'linters',
        timeout: 180,
    )

    black_exe = find_program('black')
    test('black',
        py,
        args: [black_exe.full_path(),
               '--diff', '.'],
        workdir: source_root,
        suite: 'linters',
        timeout: 180,
    )
endif

py_exe = find_program('python3')
test('pytest',
    py_exe,
    args: ['-m', 'pytest', '-x'],
    workdir: source_root,
    is_parallel: false,
    suite: 'integration',
    timeout: 6720, # set to -1 once we can bump minimum Meson version to 0.58
)
