# Meson definition for Laniakea - lk-admin

lk_admin_src = [
    'admintool.d',
    'baseadmin.d',
    'planteradmin.d',
    'spearsadmin.d',
    'syncadmin.d',
    'isotopeadmin.d'
]

lk_admin_exe = executable ('lk-admin',
    ['app.d',
     lk_admin_src],
    dependencies: [laniakea_shared_dep],
    install: true,
    install_dir : 'bin/'
)

# Test
lkadmin_test_exe = executable ('lk_test_self-lkadmin',
    [lk_admin_src],
    dependencies: [laniakea_shared_dep],
    d_args: d_unittest_args,
    link_args: '-main'
)
test('lk_test_self-lkadmin', lkadmin_test_exe)
