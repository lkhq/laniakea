project('Laniakea', 'c',
    meson_version: '>=0.48',
    license: 'LGPL-3.0+',
    version: '0.1'
)

source_root = meson.source_root()
build_root  = meson.build_root()

pymod = import('python')
py = pymod.find_installation('python3')

#
# Dependencies
#
systemd_dep = dependency('systemd')

# Python deps
r = run_command('./check_modules.py', 'base')
if r.returncode() != 0
    message(r.stdout().strip()+'\n'+r.stderr().strip())
    error('Unable to find required Python modules.')
endif

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
