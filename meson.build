project('Laniakea', 'd')

source_root = meson.source_root()

laniakea_lib_src = [
    'src/c/libarchive.d',
    'src/laniakea/config.d',
    'src/laniakea/compressed.d',
    'src/laniakea/downloadmanager.d',
    'src/laniakea/pkgitems.d',
    'src/laniakea/logging.d',
    'src/laniakea/net.d',
    'src/laniakea/tagfile.d',
    'src/laniakea/repository/dak.d',
    'src/laniakea/repository/package.d',
    'src/laniakea/repository/dscfile.d',
    'src/laniakea/repository/repository.d',
    'src/laniakea/utils/consts.d',
    'src/laniakea/utils/gpg.d',
    'src/laniakea/utils/package.d',
    'src/laniakea/utils/utils.d',
    'src/laniakea/utils/versioncmp.d'
]

cthulhu_src = []

frontend_src = ['src/frontend/source/app.d']

synchrotron_src = ['src/synchrotron/syncengine.d']

spears_src = ['src/spears/spearsengine.d',
              'src/spears/britneyconfig.d'
]

src_dir = include_directories('src/')

#
# Dependencies
#
crypto_dep = dependency('libcrypto')
ssl_dep = dependency('libssl')
archive_dep = dependency('libarchive')
curl_dep = dependency('libcurl')

#
# Build Laniakea and its modules
#
base_deps = [crypto_dep,
             ssl_dep,
             archive_dep,
             curl_dep]

laniakea_lib = static_library ('laniakea',
    [laniakea_lib_src],
    include_directories: [src_dir],
    dependencies: [base_deps]
)

cthulhu_exe = executable ('cthulhu',
    ['src/cthulhu/app.d',
     cthulhu_src],
    include_directories: [src_dir],
    link_with: [laniakea_lib],
    dependencies: [base_deps],
    install: true,
    install_dir : 'lib/laniakea/'
)

synchrotron_exe = executable ('synchrotron',
    ['src/synchrotron/app.d',
     synchrotron_src],
    include_directories: [src_dir],
    link_with: [laniakea_lib],
    dependencies: [base_deps],
    install: true
)

spears_exe = executable ('spears',
    ['src/spears/app.d',
     spears_src],
    include_directories: [src_dir],
    link_with: [laniakea_lib],
    dependencies: [base_deps],
    install: true,
    install_dir : 'lib/laniakea/'
)

#
# Tests
#
tests_src_dir = include_directories('tests/')

tests_src = [
    'tests/runner.d',
    'tests/testutils.d',
    'tests/repotests.d',
    'tests/gpgtests.d'
]

main_test_exe = executable ('main_test',
    [tests_src,
     laniakea_lib_src,
     synchrotron_src],
    include_directories: [src_dir, tests_src_dir],
    dependencies: [base_deps],
    d_args: meson.get_compiler('d').unittest_args()
)
test('laniakea_main_test', main_test_exe, args: [source_root + '/tests/data'])
