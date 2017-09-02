# Meson definition for Laniakea - Rubicon

rubicon_src = [
    'fileimport.d',
    'rubiconfig.d',
    'importisotope.d'
]

rubicon_exe = executable ('rubicon',
    ['app.d',
     rubicon_src],
    dependencies: [laniakea_shared_dep],
    install: true,
    install_dir: lk_priv_bin_target
)

# Test
rubicon_test_exe = executable ('lk_test_self-rubicon',
    [rubicon_src],
    dependencies: [laniakea_shared_dep],
    d_args: d_unittest_args,
    link_args: '-main'
)
test('lk_test_self-rubicon', rubicon_test_exe)
