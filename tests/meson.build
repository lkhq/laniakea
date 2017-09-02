# Meson definition for Laniakea System and Integration tests

tests_src_dir = include_directories('')

lk_tests_src = [
    'runner.d',
    'testutils.d',
    'repotests.d',
    'gpgtests.d'
   # 'test_spears.d'
]

lk_main_test_exe = executable ('lk-test_integration',
    [lk_tests_src],
    dependencies: [laniakea_shared_dep]
)
test('lk-test_integration',
    lk_main_test_exe,
    args: [join_paths(source_root, 'tests', 'data')]
)
