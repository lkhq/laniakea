# Meson definition for Laniakea - Shared
add_languages('c')

laniakea_lib_src = [
    'cmdargs.d',
    'compressed.d',
    'config/core.d',
    'config/isotope.d',
    'config/jobs.d',
    'config/package.d',
    'config/spears.d',
    'config/workers.d',
    'debcheck.d',
    'downloadmanager.d',
    'git.d',
    'localconfig.d',
    'logging.d',
    'net.d',
    'repository/dak.d',
    'repository/dscfile.d',
    'repository/package.d',
    'repository/repository.d',
    'repository/types.d',
    'tagfile.d',
    'utils/consts.d',
    'utils/gpg.d',
    'utils/namegen.d',
    'utils/package.d',
    'utils/utils.d',
    'utils/versioncmp.d',
    'py/druntime.c'
]

lknative_py_src = [
    'py/pyhelper.d',
    'py/pywrap.d'
]

lk_base_deps = [crypto_dep,
                ssl_dep,
                dcontainers_dep,
                archive_dep,
                curl_dep,
                czmq_dep,
                dyaml_dep,
                vibe_core_dep,
                vibe_data_dep,
                glibd_dep,
                appstream_dep
]

laniakea_lib = shared_library('laniakea',
    [laniakea_lib_src],
    include_directories: [lkshared_src_dir, src_dir],
    link_with: [lk_cbind_lib],
    dependencies: [lk_base_deps, girbinding_dep],
    d_args: ['-J' + source_root + '/data/']
)

laniakea_shared_dep = declare_dependency(
    dependencies: [lk_base_deps],
    link_with: [laniakea_lib],
    include_directories: [lkshared_src_dir, gir_bind_dir, src_dir],
)

lknative_pylib = shared_library('lknative',
    [lknative_py_src],
    name_prefix: '',
    dependencies: [pyd_dep, laniakea_shared_dep]
)

# Test
lk_shared_test_exe = executable ('lk_test_self-core',
    [laniakea_lib_src],
    include_directories: [lkshared_src_dir, src_dir, gir_bind_dir],
    link_with: [lk_cbind_lib],
    dependencies: [lk_base_deps, girbinding_dep],
    d_args: d_unittest_args + ['-J' + source_root + '/data/'],
    link_args: '-main',
)
test('lk_test_self-core', lk_shared_test_exe)
