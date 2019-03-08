# Meson definition for Laniakea - Shared

lknative_src = [
    'cmdargs.d',
    'config/core.d',
    'config/isotope.d',
    'config/package.d',
    'config/spears.d',
    'config/synchrotron.d',
    'debcheck.d',
    'downloadmanager.d',
    'py/pyhelper.d',
    'py/pywrap.d',
    'synchrotron/package.d',
    'synchrotron/syncengine.d',
    'spears/package.d',
    'spears/spearsengine.d',
    'spears/britneyconfig.d',
    'spears/britney.d',
    'spears/excuses.d',
]

lknative_pylib = shared_library('lknative',
    [lknative_src],
    name_prefix: '',
    include_directories: [lknative_src_dir],
    dependencies: [laniakea_utils_dep, pyd_dep]
)

# Test
lk_pynative_test_exe = executable ('lk_test_self-lknative',
    [lknative_src],
    dependencies: [laniakea_utils_dep],
    include_directories: [lknative_src_dir],
    d_args: d_unittest_args + ['-J' + source_root + '/data/'],
    link_args: '-main',
)
test('lk_test_self-lknative', lk_pynative_test_exe)
