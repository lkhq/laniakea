project('Laniakea', 'd', meson_version: '>=0.40.0')

source_root = meson.source_root()

#
# Dependencies
#
crypto_dep = dependency('libcrypto')
ssl_dep = dependency('libssl')
archive_dep = dependency('libarchive')
curl_dep = dependency('libcurl')
czmq_dep = dependency('libczmq')
dyaml_dep = dependency('dyaml')
systemd_dep = dependency('systemd')

# Vibe
vibe_core_dep = dependency('vibe-core')
vibe_data_dep = dependency('vibe-data')
vibe_mongo_dep = dependency('vibe-mongodb')

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
#foreach s : (laniakea_lib_src + lkadmin_src + synchrotron_src + spears_src + eggshell_src)
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
