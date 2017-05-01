project('Laniakea', 'd', meson_version: '>=0.40.0')

source_root = meson.source_root()

cbind_src = [
    'src/c/libarchive.d',
    'src/c/zmq/zframe.d',
    'src/c/zmq/zclock.d',
    'src/c/zmq/zgossip.d',
    'src/c/zmq/zstr.d',
    'src/c/zmq/zloop.d',
    'src/c/zmq/zhashx.d',
    'src/c/zmq/zcertstore.d',
    'src/c/zmq/zlistx.d',
    'src/c/zmq/zsock.d',
    'src/c/zmq/czmq_library.d',
    'src/c/zmq/czmq_prelude.d',
    'src/c/zmq/zproxy.d',
    'src/c/zmq/zrex.d',
    'src/c/zmq/czmq.d',
    'src/c/zmq/zchunk.d',
    'src/c/zmq/zmsg.d',
    'src/c/zmq/zcert.d',
    'src/c/zmq/zarmour.d',
    'src/c/zmq/zhash.d',
    'src/c/zmq/zsys.d',
    'src/c/zmq/zdigest.d',
    'src/c/zmq/zauth.d',
    'src/c/zmq/zfile.d',
    'src/c/zmq/zdir_patch.d',
    'src/c/zmq/zmonitor.d',
    'src/c/zmq/ziflist.d',
    'src/c/zmq/zbeacon.d',
    'src/c/zmq/zlist.d',
    'src/c/zmq/zmq.d',
    'src/c/zmq/package.d',
    'src/c/zmq/zpoller.d',
    'src/c/zmq/zuuid.d',
    'src/c/zmq/zactor.d',
    'src/c/zmq/zconfig.d',
    'src/c/zmq/zdir.d'
]

laniakea_lib_src = [
    'src/laniakea/localconfig.d',
    'src/laniakea/compressed.d',
    'src/laniakea/debcheck.d',
    'src/laniakea/downloadmanager.d',
    'src/laniakea/git.d',
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
    'src/laniakea/utils/versioncmp.d',
    'src/laniakea/utils/namegen.d',
    'src/laniakea/db/package.d',
    'src/laniakea/db/database.d',
    'src/laniakea/db/schema/package.d',
    'src/laniakea/db/schema/basic.d',
    'src/laniakea/db/schema/jobs.d',
    'src/laniakea/db/schema/debcheck.d',
    'src/laniakea/db/schema/synchrotron.d',
    'src/laniakea/db/schema/spears.d',
    'src/laniakea/db/schema/eggshell.d',
    'src/laniakea/db/schema/workers.d',
    'src/laniakea/db/schema/isotope.d'
]

lkadmin_src = [
    'src/admin/admintool.d',
    'src/admin/baseadmin.d',
    'src/admin/eggshelladmin.d',
    'src/admin/spearsadmin.d',
    'src/admin/syncadmin.d',
    'src/admin/isotopeadmin.d'
]

keytool_src = [
    'src/keytool/zcurveutils.d'
]

lighthouse_src = [
    'src/lighthouse/server.d',
    'src/lighthouse/utils.d',
    'src/lighthouse/worker.d'
]

cthulhu_src = []

synchrotron_src = ['src/synchrotron/syncengine.d']

spears_src = ['src/spears/spearsengine.d',
              'src/spears/britneyconfig.d',
              'src/spears/britney.d',
              'src/spears/excuses.d',
]

eggshell_src = ['src/eggshell/germinate.d']

rubicon_src = [
    'src/rubicon/fileimport.d',
    'src/rubicon/rubiconfig.d',
    'src/rubicon/importisotope.d'
]

src_dir = include_directories('src/')

#
# Dependencies
#
crypto_dep = dependency('libcrypto')
ssl_dep = dependency('libssl')
archive_dep = dependency('libarchive')
curl_dep = dependency('libcurl')
czmq_dep = dependency('libczmq')
dyaml_dep = dependency('dyaml')

# Vibe
vibe_core_dep = dependency('vibe-core')
vibe_data_dep = dependency('vibe-data')
vibe_mongo_dep = dependency('vibe-mongodb')

#
# Build Laniakea and its modules
#
base_deps = [crypto_dep,
             ssl_dep,
             archive_dep,
             curl_dep,
             czmq_dep,
             dyaml_dep,
             vibe_core_dep,
             vibe_data_dep,
             vibe_mongo_dep]

cbindings_lib = static_library ('lkcbind',
    [cbind_src],
    include_directories: [src_dir],
    dependencies: [base_deps]
)

laniakea_lib = static_library ('laniakea',
    [laniakea_lib_src],
    include_directories: [src_dir],
    link_with: [cbindings_lib],
    dependencies: [base_deps],
    d_args: '-J' + source_root + '/data/'
)

lighthouse_exe = executable ('lighthouse',
    ['src/lighthouse/app.d',
     lighthouse_src],
    include_directories: [src_dir],
    link_with: [laniakea_lib],
    dependencies: [base_deps],
    install: true,
    install_dir: 'lib/laniakea/'
)

lkadmin_exe = executable ('lk-admin',
    ['src/admin/app.d',
     lkadmin_src],
    include_directories: [src_dir],
    link_with: [laniakea_lib],
    dependencies: [base_deps],
    install: true,
    install_dir : 'bin/'
)

keytool_exe = executable ('lk-keytool',
    ['src/keytool/app.d',
     keytool_src],
    include_directories: [src_dir],
    link_with: [laniakea_lib],
    dependencies: [base_deps],
    install: true,
    install_dir : 'bin/'
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
    install_dir: 'lib/laniakea/'
)

eggshell_exe = executable ('eggshell',
    ['src/eggshell/app.d',
     eggshell_src],
    include_directories: [src_dir],
    link_with: [laniakea_lib],
    dependencies: [base_deps],
    install: true,
    install_dir: 'lib/laniakea/'
)

debcheck_exe = executable ('debcheck',
    ['src/debcheck/app.d'],
    include_directories: [src_dir],
    link_with: [laniakea_lib],
    dependencies: [base_deps],
    install: true,
    install_dir: 'lib/laniakea/'
)

rubicon_exe = executable ('rubicon',
    ['src/rubicon/app.d',
     rubicon_src],
    include_directories: [src_dir],
    link_with: [laniakea_lib],
    dependencies: [base_deps],
    install: true,
    install_dir: 'lib/laniakea/'
)

#
# Web frontend
#
opt_webgui = get_option('webgui')
if (opt_webgui)
    subdir('src/web')
endif

#
# Data
#
subdir('data')

#
# Tests
#
tests_src_dir = include_directories('tests/')

tests_src = [
    'tests/runner.d',
    'tests/testutils.d',
    'tests/repotests.d',
    'tests/gpgtests.d',
    'tests/test_spears.d'
]

main_test_exe = executable ('main_test',
    [tests_src,
     laniakea_lib_src,
     lkadmin_src,
     synchrotron_src,
     spears_src,
     eggshell_src],
    include_directories: [src_dir, tests_src_dir],
    link_with: [cbindings_lib],
    dependencies: [base_deps, dyaml_dep],
    build_by_default: false,
    d_args: meson.get_compiler('d').unittest_args() +
             ['-J' + source_root + '/data/']
)
test('laniakea_main_test', main_test_exe, args: [source_root + '/tests/data'])

#
# Documentation
#
doc_sources = []
foreach s : (laniakea_lib_src + lkadmin_src + synchrotron_src + spears_src + eggshell_src)
  doc_sources += source_root + '/' + s
endforeach

docs_target = custom_target('documentation',
  output : 'documentation.fake',
  input : laniakea_lib_src,
  command : ['ldc2', '-D', '-dw', '-c', '-o-',
             '-Dd=docs/', '-Xf=docs/documentation.json', doc_sources, '-I', source_root + '/src',
             '-I/usr/include/d/vibe', '-I/usr/local/include/d/', '-oq']
)
