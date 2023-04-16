# Meson definition for Laniakea - Shared Python Module

install_subdir(
    '.',
    install_dir: py.get_install_dir() / 'laniakea',
    exclude_directories: ['__pycache__'],
    exclude_files: ['meson.build'],
    strip_directory: true
)
install_symlink(
    'laniakea',
    install_dir: 'lib/laniakea',
    pointing_to: py.get_install_dir() / 'laniakea',
)

apt_ftparchive_exe = find_program('apt-ftparchive', required: false)
if not apt_ftparchive_exe.found()
    error('Unable to find `apt-ftparchive`. Please install `apt-utils` to continue.')
endif

bwrap_exe = find_program('bwrap', required: false)
if not bwrap_exe.found()
    error('Unable to find `bwrap`. Please install `bubblewrap` to continue.')
endif
