# Meson definition for Laniakea - mIrk

# Additional Python deps
r = run_command(pymod_check_exe, [pymod_check_arg, 'matrix'], check: false)
if r.returncode() != 0
    error(r.stderr().strip())
endif

install_subdir('.', install_dir: 'lib/laniakea/mirk/',
    exclude_directories: ['__pycache__'],
    exclude_files: ['meson.build'],
)
