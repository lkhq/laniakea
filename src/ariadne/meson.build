# Meson definition for Laniakea - Ariadne

ariadne_src = ['buildscheduler.d']

ariadne_exe = executable ('ariadne',
    ['app.d',
     ariadne_src],
    dependencies: [laniakea_shared_dep],
    install: true,
    install_dir : lk_priv_bin_target
)

# Test
ariadne_test_exe = executable ('lk_test_self-ariadne',
    [ariadne_src],
    dependencies: [laniakea_shared_dep],
    d_args: d_unittest_args,
    link_args: '-main'
)
test('lk_test_self-ariadne', ariadne_test_exe)
