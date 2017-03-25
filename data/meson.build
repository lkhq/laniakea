 
opt_webgui = get_option('webgui')
if (opt_webgui)
    sd_dep = dependency('systemd')

    sd_data = configuration_data()
    sd_data.set('LKWEB_INSTALL_BIN', get_option('prefix') + '/lib/laniakea/web/laniakea-web')

    configure_file(input: 'laniakea-web.service.in',
                   output: 'laniakea-web.service',
                   configuration: sd_data)

    install_data(meson.current_build_dir() + '/laniakea-web.service', install_dir: sd_dep.get_pkgconfig_variable('systemdsystemunitdir'))

endif
