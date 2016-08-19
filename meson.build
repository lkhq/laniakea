project('Laniakea', 'd')


laniakea_lib_src = [
    'src/laniakea/archive.d',
    'src/c/libarchive.d',
    'src/laniakea/config.d',
    'src/laniakea/downloadmanager.d',
    'src/laniakea/logging.d',
    'src/laniakea/repository/dak.d',
    'src/laniakea/repository/packages.d',
    'src/laniakea/repository/repository.d',
    'src/laniakea/utils/consts.d',
    'src/laniakea/utils/package.d',
    'src/laniakea/utils/tagfile.d',
    'src/laniakea/utils/utils.d',

    'src/requests/base.d',
    'src/requests/ftp.d',
    'src/requests/http.d',
    'src/requests/package.d',
    'src/requests/streams.d',
    'src/requests/uri.d',
    'src/requests/utils.d'
]

#
# Dependencies
#
crypto_dep = dependency('libcrypto')
ssl_dep = dependency('libssl')
archive_dep = dependency('libarchive')

frontend_src = ['src/frontend/source/app.d']

synchrotron_src = ['src/synchrotron/app.d', 'src/synchrotron/syncengine.d']

src_dir = gir_bind_dir = include_directories('src/')

synchrotron_exe = executable ('synchrotron',
    [laniakea_lib_src, synchrotron_src],
    include_directories : [src_dir],
    dependencies : [crypto_dep,
    		    ssl_dep,
    		    archive_dep],
    install : true
)
