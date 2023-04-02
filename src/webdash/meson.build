# Meson definition for Laniakea - Web Dashboard UI

install_subdir('.', install_dir: 'lib/laniakea/webdash/',
    exclude_directories: ['__pycache__', 'lkweb/__pycache__'],
    exclude_files: ['meson.build', '.gitignore', 'lkwebdash.ini.in'],
)

wd_data = configuration_data()
if get_option('virtualenv') != ''
    wd_data.set('LK_VIRTUALENV_HOME_ENTRY', 'home = ' + get_option('virtualenv').strip())
endif

configure_file(
    input: 'lkwebdash.ini.in',
    output: 'lkwebdash.ini',
    configuration: wd_data,
    install_dir: 'lib/laniakea/webdash/',
)
