# Meson definition for Laniakea - DataImport

dataimport_src = ['repodbimport.d']

version_flags = ''
if (get_option('experimental-appstream'))
    version_flags = '-d-version=ExperimentalAppStream'
endif

dataimport_exe = executable ('lk-dataimport',
    ['app.d',
     dataimport_src],
    dependencies: [laniakea_shared_dep],
    d_args: [version_flags],
    install: true,
    install_dir: lk_priv_bin_target
)

# Test
dataimport_test_exe = executable ('lk_test_self-dataimport',
    [dataimport_src],
    dependencies: [laniakea_shared_dep],
    d_args: d_unittest_args + [version_flags],
    link_args: '-main'
)
test('lk_test_self-dataimport', dataimport_test_exe)
