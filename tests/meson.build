# Meson definition for Laniakea System and Integration tests

#tests_src_dir = include_directories('')
#
#lk_tests_src = [
#    'runner.d',
#    'testutils.d',
#    'repotests.d',
#    'gpgtests.d'
#   # 'test_spears.d'
#]
#
#lk_main_test_exe = executable ('lk-test_integration',
#    [lk_tests_src],
#    dependencies: [laniakea_shared_dep, fluentasserts_dep]
#)
#test('lk-test_integration',
#    lk_main_test_exe,
#    args: [join_paths(source_root, 'tests', 'test_data')]
#)

py_exe = find_program('python3')
test('pytest',
    py_exe,
    args: ['-m', 'pytest'],
    workdir: source_root,
    is_parallel: false
)

if (get_option('test-flake8'))
    flake8_exe = find_program('flake8')
    test('flake8',
         flake8_exe,
         args: ['--ignore', 'E501,E402',
                source_root]
    )
endif

if (get_option('test-dscanner'))
    dscanner_exe = find_program('dscanner')
    run_dscanner_exe = find_program(join_paths(source_root, 'tests', 'ci', 'run-dscanner.py'))
    test('dscanner',
         run_dscanner_exe,
         args: [source_root, 'tests/ci/dscanner.ini']
    )
endif
