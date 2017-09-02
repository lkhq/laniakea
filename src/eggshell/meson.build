# Meson definition for Laniakea - Eggshell

eggshell_src = ['germinate.d']

eggshell_exe = executable ('eggshell',
    ['app.d',
     eggshell_src],
    dependencies: [laniakea_shared_dep],
    install: true,
    install_dir: lk_priv_bin_target
)

# Test
eggshell_test_exe = executable ('lk_test_self-eggshell',
    [eggshell_src],
    dependencies: [laniakea_shared_dep],
    d_args: d_unittest_args,
    link_args: '-main'
)
test('lk_test_self-eggshell', eggshell_test_exe)
