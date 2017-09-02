# Meson definition for Laniakea - lk-keytool

keytool_src = [
    'zcurveutils.d'
]

keytool_exe = executable ('lk-keytool',
    ['app.d',
     keytool_src],
    dependencies: [laniakea_shared_dep],
    install: true
)

# Test
keytool_test_exe = executable ('lk_test_self-keytool',
    [keytool_src],
    dependencies: [laniakea_shared_dep],
    d_args: d_unittest_args,
    link_args: '-main'
)
test('lk_test_self-keytool', keytool_test_exe)
