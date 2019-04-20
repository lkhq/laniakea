project('Laniakea', 'd',
    meson_version: '>=0.46',
    subproject_dir: 'contrib/subprojects',
    license: 'GPL-3.0+',
    version: '0.1'
)

source_root = meson.source_root()
build_root  = meson.build_root()

pymod = import('python')
py = pymod.find_installation('python3')

#
# Dependencies
#
archive_dep = dependency('libarchive')
curl_dep = dependency('libcurl')
systemd_dep = dependency('systemd')
dcontainers_dep = dependency('dcontainers', version: '>= 0.8.0', fallback: ['dcontainers', 'dcontainers_dep'])
dyaml_dep = dependency('dyaml', version: '>= 0.6', fallback: ['dyaml', 'dyaml_dep'])
pyd_dep = dependency('pyd')

# Python deps
r = run_command('./check_modules.py')
if r.returncode() != 0
    message(r.stdout().strip())
    error('Unable to find required Python modules.')
endif

#
# Common D Features
#
dc = meson.get_compiler('d')

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
