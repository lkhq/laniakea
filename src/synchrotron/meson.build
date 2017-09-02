# Meson definition for Laniakea - Synchrotron

synchrotron_src = [
    'syncengine.d'
]

synchrotron_exe = executable ('synchrotron',
    ['app.d',
     synchrotron_src],
    dependencies: [laniakea_shared_dep],
    install: true
)

# Test
synchrotron_test_exe = executable ('lk_test_self-synchrotron',
    [synchrotron_src],
    dependencies: [laniakea_shared_dep],
    d_args: d_unittest_args,
    link_args: '-main'
)
test('lk_test_self-synchrotron', synchrotron_test_exe)
