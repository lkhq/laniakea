# Meson definition for Laniakea - Shared Utility Library

add_languages('c')

laniakea_ulib_src = [
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
]

lk_base_deps = [dcontainers_dep,
                archive_dep,
                curl_dep,
                dyaml_dep
]

laniakea_utils_lib = shared_library('laniakea-shared',
    [laniakea_ulib_src, 'druntime.c'],
    include_directories: [src_dir],
    dependencies: [lk_base_deps],
    d_import_dirs: [source_root + '/data/'],
    install: true
)

laniakea_utils_dep = declare_dependency(
    dependencies: [lk_base_deps],
    link_with: [laniakea_utils_lib],
    include_directories: [src_dir],
)

# Test
lk_shared_test_exe = executable ('lk_test_self-shared',
    [laniakea_ulib_src],
    include_directories: [src_dir],
    dependencies: [lk_base_deps],
    d_import_dirs: [source_root + '/data/'],
    d_unittest: true,
    link_args: '-main',
)
test('lk_test_self-shared', lk_shared_test_exe)
