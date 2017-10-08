# Meson definition for Laniakea - Planter

planter_src = ['germinate.d']

planter_exe = executable ('planter',
    ['app.d',
     planter_src],
    dependencies: [laniakea_shared_dep],
    install: true,
    install_dir: lk_priv_bin_target
)

# Test
planter_test_exe = executable ('lk_test_self-planter',
    [planter_src],
    dependencies: [laniakea_shared_dep],
    d_args: d_unittest_args,
    link_args: '-main'
)
test('lk_test_self-planter', planter_test_exe)
