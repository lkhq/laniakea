project('Laniakea', 'c',
    meson_version: '>=1.0',
    license: 'LGPL-3.0+',
    version: '0.1'
)

source_root = meson.project_source_root()
build_root  = meson.project_build_root()

pymod = import('python')
py = pymod.find_installation('python3')

#
# Dependencies
#
python_min_version = '3.11'
systemd_dep = dependency('systemd')

if not py.language_version().version_compare('>=' + python_min_version)
    error('Python version is too low. We require at least ' + python_min_version + ' to run.')
endif

# Python dependencies
pymod_check_exe = find_program(join_paths(source_root, 'pyreqcheck.py'))
pymod_check_arg = ['--check-group']
r = run_command(pymod_check_exe, [pymod_check_arg, 'base'], check: false)
if r.returncode() != 0
    error(r.stderr().strip())
endif

# maintainer target to update requirements files
run_target ('update-requirements',
    command: [pymod_check_exe, ['--write-requirements']]
)

if build_machine.system() != 'linux'
    error('Laniakea needs Linux and GLibc to work properly, as it relies on system calls like renameat2 to function properly.')
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

#
# Documentation
#
if get_option('docs')
    subdir('docs')
endif
