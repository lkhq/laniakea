# Meson definition for Laniakea - Spears

spears_src = [
    'spearsengine.d',
    'britneyconfig.d',
    'britney.d',
    'excuses.d',
]

spears_exe = executable ('spears',
    ['app.d',
     spears_src],
    dependencies: [laniakea_shared_dep],
    install: true,
    install_dir: lk_priv_bin_target
)

# Test
spears_test_exe = executable ('lk_test_self-spears',
    [spears_src],
    dependencies: [laniakea_shared_dep],
    d_args: d_unittest_args,
    link_args: '-main'
)
test('lk_test_self-spears', spears_test_exe)
