# Meson definition for Laniakea - mIrk

# Additional Python deps
r = run_command('../../check_modules.py', 'matrix')
if r.returncode() != 0
    message(r.stdout().strip()+'\n'+r.stderr().strip())
    error('Unable to find required Python modules.')
endif

install_subdir('.', install_dir: 'lib/laniakea/mirk/',
    exclude_directories: ['__pycache__', 'mirk/__pycache__'],
    exclude_files: ['meson.build'],
)
