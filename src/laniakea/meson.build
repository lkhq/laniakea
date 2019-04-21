# Meson definition for Laniakea - Shared Python Module

lknative_src_dir = include_directories('.')

subdir('lknative')

install_subdir('.', install_dir: 'lib/laniakea/laniakea',
    exclude_directories: ['__pycache__', 'lknative'],
    exclude_files: ['meson.build'],
    strip_directory: true
)
