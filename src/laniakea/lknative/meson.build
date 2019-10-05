# Meson definition for Laniakea - Shared

lknative_src = [
    'c/libarchive.d',
    'compressed.d',
    'git.d',
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

    'config/core.d',
    'config/package.d',
    'config/spears.d',
    'config/synchrotron.d',
    'debcheck.d',
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

lknative_deps = [pyd_dep,
                 archive_dep,
                 curl_dep,
                 dyaml_dep
]

lkdrcompat_lib = static_library('lkdrcompat', 'druntime.c')
data_import_dir = include_directories('../../../data/')

lknative_pylib = shared_library('lknative',
    [lknative_src],
    name_prefix: '',
    include_directories: [lknative_src_dir],
    dependencies: lknative_deps,
    objects: lkdrcompat_lib.extract_objects('druntime.c'),
    d_import_dirs: [data_import_dir],
    install: true,
    install_dir : 'lib/laniakea/laniakea/'
)

# Test
lk_pynative_test_exe = executable ('lk_test_lknative',
    [lknative_src],
    dependencies: lknative_deps,
    include_directories: [lknative_src_dir],
    d_import_dirs: [data_import_dir],
    d_unittest: true,
    link_args: '-main',
)
test('lknative',
     lk_pynative_test_exe,
     is_parallel: false
)
