# Meson definition for Laniakea - Web UI

install_subdir('.', install_dir: 'lib/laniakea/webswview/',
    exclude_directories: ['__pycache__', 'lkweb/__pycache__'],
    exclude_files: ['meson.build',
                    'lkwebswview.ini.in',
                    'templates/default/.gitignore',
                    'templates/pureos/.gitignore'],
)

wsw_data = configuration_data()
wsw_data.set('LK_VIRTUALENV_HOME_ENTRY', '')
if get_option('virtualenv') != ''
    wsw_data.set('LK_VIRTUALENV_HOME_ENTRY', 'home = ' + get_option('virtualenv').strip())
endif

configure_file(
    input: 'lkwebswview.ini.in',
    output: 'lkwebswview.ini',
    configuration: wsw_data,
    install_dir: 'lib/laniakea/webswview/',
)
