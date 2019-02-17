# Meson definition for Laniakea - Shared Utility Library

add_languages('c')

lk_cbind_src = [
    'c/libarchive.d',
    'c/zmq/zframe.d',
    'c/zmq/zclock.d',
    'c/zmq/zgossip.d',
    'c/zmq/zstr.d',
    'c/zmq/zloop.d',
    'c/zmq/zhashx.d',
    'c/zmq/zcertstore.d',
    'c/zmq/zlistx.d',
    'c/zmq/zsock.d',
    'c/zmq/czmq_library.d',
    'c/zmq/czmq_prelude.d',
    'c/zmq/zproxy.d',
    'c/zmq/zrex.d',
    'c/zmq/czmq.d',
    'c/zmq/zchunk.d',
    'c/zmq/zmsg.d',
    'c/zmq/zcert.d',
    'c/zmq/zarmour.d',
    'c/zmq/zhash.d',
    'c/zmq/zsys.d',
    'c/zmq/zdigest.d',
    'c/zmq/zauth.d',
    'c/zmq/zfile.d',
    'c/zmq/zdir_patch.d',
    'c/zmq/zmonitor.d',
    'c/zmq/ziflist.d',
    'c/zmq/zbeacon.d',
    'c/zmq/zlist.d',
    'c/zmq/zmq.d',
    'c/zmq/package.d',
    'c/zmq/zpoller.d',
    'c/zmq/zuuid.d',
    'c/zmq/zactor.d',
    'c/zmq/zconfig.d',
    'c/zmq/zdir.d'
]

laniakea_ulib_src = [
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

lk_cbind_lib = static_library ('lkcbind',
    [lk_cbind_src],
    include_directories: [src_dir],
    dependencies: [archive_dep,
                   czmq_dep]
)

lk_base_deps = [crypto_dep,
                ssl_dep,
                dcontainers_dep,
                archive_dep,
                curl_dep,
                czmq_dep,
                dyaml_dep,
                glibd_dep,
                appstream_dep
]

laniakea_utils_lib = shared_library('laniakea-shared',
    [laniakea_ulib_src, 'druntime.c'],
    include_directories: [src_dir],
    link_with: [lk_cbind_lib],
    dependencies: [lk_base_deps, girbinding_dep],
    d_import_dirs: [source_root + '/data/']
)

laniakea_utils_dep = declare_dependency(
    dependencies: [lk_base_deps],
    link_with: [laniakea_utils_lib],
    include_directories: [src_dir, gir_bind_dir],
)

# Test
lk_shared_test_exe = executable ('lk_test_self-shared',
    [laniakea_ulib_src],
    include_directories: [src_dir, gir_bind_dir],
    link_with: [lk_cbind_lib],
    dependencies: [lk_base_deps, girbinding_dep],
    d_args: d_unittest_args + ['-J' + source_root + '/data/'],
    link_args: '-main',
)
test('lk_test_self-shared', lk_shared_test_exe)
