# Meson definition for Laniakea - Rubicon

install_subdir('.', install_dir: 'lib/laniakea/rubicon/',
    exclude_directories: ['__pycache__'],
    exclude_files: ['meson.build', 'rubicon'],
)

if get_option('virtualenv') != ''
    vbin_data = configuration_data()
    vbin_data.set('LK_VIRTUALENV_DIR', get_option('virtualenv').strip())
    configure_file(
        input: 'rubicon.in',
        output: 'rubicon',
        configuration: vbin_data,
        install_dir: 'bin',
    )
else
    install_data('rubicon', install_dir: 'bin', rename: 'rubicon')
endif
