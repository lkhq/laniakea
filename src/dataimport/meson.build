# Meson definition for Laniakea - DataImport

dataimport_src = ['repodbimport.d']

dataimport_exe = executable ('lk-dataimport',
    ['app.d',
     dataimport_src],
    dependencies: [laniakea_shared_dep],
    install: true,
    install_dir : lk_priv_bin_target
)

# Test
dataimport_test_exe = executable ('lk_test_self-dataimport',
    [dataimport_src],
    dependencies: [laniakea_shared_dep],
    d_args: d_unittest_args,
    link_args: '-main'
)
test('lk_test_self-dataimport', dataimport_test_exe)
