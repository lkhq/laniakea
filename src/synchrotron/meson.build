# Meson definition for Laniakea - Synchrotron

synchrotron_src = [
    'syncengine.d',
    'pywrap.d',
    'syncconfig.d',
    '../laniakea/lknative/py/pyhelper.d'
]

synchrontron_pylib = shared_library('lknative_synchrotron',
    [synchrotron_src],
    name_prefix: '',
    dependencies: [pyd_dep, laniakea_shared_dep]
)

# Test
#synchrotron_test_exe = executable ('lk_test_self-synchrotron',
#    [synchrotron_src],
#    dependencies: [laniakea_shared_dep],
#    d_args: d_unittest_args,
#    link_args: '-main'
#)
#test('lk_test_self-synchrotron', synchrotron_test_exe)
