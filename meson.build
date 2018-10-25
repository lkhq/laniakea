project('Laniakea', 'd',
    meson_version: '>=0.46',
    subproject_dir: 'contrib/subprojects',
    license: 'GPL-3.0+',
    version: '0.1'
)

source_root = meson.source_root()
build_root  = meson.build_root()

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
autowrap_py_dep = dependency('autowrap-python')

glibd_dep = dependency('glibd-2.0', fallback: ['glibd', 'glibd_dep'])
appstream_dep = dependency('appstream')

# Vibe
vibe_core_dep = dependency('vibe-core')
vibe_data_dep = dependency('vibe-data')

#
# Common D Features
#
dc = meson.get_compiler('d')
d_unittest_args = dc.unittest_args() # dc.feature_args(unittest: true)

#
# GIR wrapping
#
subdir('contrib/wrap')

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
#subdir('tests')
