# Meson definition for Laniakea - DataSync

datasync_src = ['repodbsync.d']

datasync_exe = executable ('lk-datasync',
    ['app.d',
     datasync_src],
    dependencies: [laniakea_shared_dep],
    install: true,
    install_dir : lk_priv_bin_target
)

# Test
datasync_test_exe = executable ('lk_test_self-datasync',
    [datasync_src],
    dependencies: [laniakea_shared_dep],
    d_args: d_unittest_args,
    link_args: '-main'
)
test('lk_test_self-datasync', datasync_test_exe)
