project('Laniakea', 'd',
    meson_version: '>=0.40.0',
    subproject_dir: 'contrib/subprojects',
    license: 'GPL-3.0+',
    version: '0.1'
)

source_root = meson.source_root()

#
# Dependencies
#
crypto_dep = dependency('libcrypto')
ssl_dep = dependency('libssl')
archive_dep = dependency('libarchive')
curl_dep = dependency('libcurl')
czmq_dep = dependency('libczmq')
systemd_dep = dependency('systemd')
dcontainers_dep = dependency('dcontainers', version: '>= 0.8.0', fallback: ['dcontainers', 'dcontainers_dep'])
dyaml_dep = dependency('dyaml', version: '>= 0.6', fallback: ['dyaml', 'dyaml_dep'])
fluentasserts_dep = dependency('fluent-asserts', version: '>= 0.6', fallback: ['fluent-asserts', 'fluentasserts_dep'])

# Database
ddbc_pg_dep = dependency('ddbc-pgsql', version: '>= 0.3.7', fallback: ['ddbc', 'ddbc_pg_dep'])
hibernated_pg_dep = dependency('hibernated-pgsql', version: '>= 0.3.2', fallback: ['hibernated', 'hibernated_pg_dep'])

# Vibe
vibe_core_dep = dependency('vibe-core')
vibe_data_dep = dependency('vibe-data')

#
# Common D Features
#
dc = meson.get_compiler('d')
d_unittest_args = dc.unittest_args() # dc.feature_args(unittest: true)

#
# Lanikaea Modules
#
subdir('src')

#
# Data
#
subdir('data')

#
# Tests
#
subdir('tests')

#
# Documentation
#

#doc_sources = []
#foreach s : (laniakea_lib_src + lkadmin_src + synchrotron_src + spears_src + planter_src)
#  doc_sources += source_root + '/' + s
#endforeach
#
#docs_target = custom_target('documentation',
#  output : 'documentation.fake',
#  input : laniakea_lib_src,
#  command : ['ldc2', '-D', '-dw', '-c', '-o-',
#             '-Dd=docs/', '-Xf=docs/documentation.json', doc_sources, '-I', source_root + '/src',
#             '-I/usr/include/d/vibe', '-I/usr/local/include/d/', '-oq']
#)
