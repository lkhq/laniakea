# Meson definition for Laniakea - Lighthouse

lighthouse_src = [
    'server.d',
    'utils.d',
    'worker.d'
]

lighthouse_exe = executable ('lighthouse',
    ['app.d',
     lighthouse_src],
    dependencies: [laniakea_shared_dep],
    install: true,
    install_dir: lk_priv_bin_target
)

# Test
lighthouse_test_exe = executable ('lk_test_self-lighthouse',
    [lighthouse_src],
    dependencies: [laniakea_shared_dep],
    d_args: d_unittest_args,
    link_args: '-main'
)
test('lk_test_self-lighthouse', lighthouse_test_exe)
