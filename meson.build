project('Laniakea', 'd')

source_root = meson.source_root()

laniakea_lib_src = [
    'src/c/libarchive.d',
    'src/laniakea/config.d',
    'src/laniakea/compressed.d',
    'src/laniakea/downloadmanager.d',
    'src/laniakea/packages.d',
    'src/laniakea/logging.d',
    'src/laniakea/tagfile.d',
    'src/laniakea/repository/dak.d',
    'src/laniakea/repository/package.d',
    'src/laniakea/repository/dscfile.d',
    'src/laniakea/repository/repository.d',
    'src/laniakea/utils/consts.d',
    'src/laniakea/utils/package.d',
    'src/laniakea/utils/utils.d'
]

#
# 3rd-party Libraries
#
find_program('git')
find_program('dub')

d_requests_dir = source_root + '/subprojects/dlang-requests'
if run_command('[', '-d', d_requests_dir, ']').returncode() != 0
    message('Fetching dlang-requests from Github...')
    git_get_requests = run_command(['git', 'clone', 'https://github.com/ikod/dlang-requests.git', d_requests_dir])
    if git_get_requests.returncode() != 0
        error('Unable to fetch dlang-requests library.\n' + git_get_requests.stderr())
    endif

    message('Building dlang-requests...')
    make_requests = run_command(['dub', 'build', '--root', d_requests_dir, '--build', 'release', '--compiler', 'ldc2'])
    if make_requests.returncode() != 0
        run_command(['rm', '--interactive=none', '-r', d_requests_dir])
        error('Unable to build dlang-requests library.\n' + make_requests.stderr())
    endif
endif
d_requests_include_dir = include_directories(d_requests_dir + '/source')
requests_lib = declare_dependency(include_directories: d_requests_include_dir,
                   link_args: ['-L-L' + d_requests_dir, '-lrequests'])

#
# Dependencies
#
crypto_dep = dependency('libcrypto')
ssl_dep = dependency('libssl')
archive_dep = dependency('libarchive')

frontend_src = ['src/frontend/source/app.d']

synchrotron_src = ['src/synchrotron/syncengine.d']

src_dir = include_directories('src/')

synchrotron_exe = executable ('synchrotron',
    [laniakea_lib_src,
     'src/synchrotron/app.d',
     synchrotron_src],
    include_directories: [src_dir],
    dependencies: [crypto_dep,
                    ssl_dep,
                    archive_dep,
                    requests_lib],
    install: true
)

#
# Tests
#

tests_src_dir = include_directories('tests/')

tests_src = [
    'tests/runner.d',
    'tests/testutils.d',
    'tests/repotests.d'
]

main_test_exe = executable ('main_test',
    [tests_src,
     laniakea_lib_src,
     synchrotron_src],
    include_directories: [src_dir, tests_src_dir],
    dependencies: [crypto_dep,
                    ssl_dep,
                    archive_dep,
                    requests_lib],
    d_args: meson.get_compiler('d').unittest_args()
)
test('laniakea_main_test', main_test_exe, args: [source_root + '/tests/data'])
