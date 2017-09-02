
current_build_dir = meson.current_build_dir()

lhsd_data = configuration_data()
lhsd_data.set('LIGHTHOUSE_INSTALL_BIN', get_option('prefix') + '/lib/laniakea/lighthouse')

configure_file(input: 'laniakea-lighthouse.service.in',
               output: 'laniakea-lighthouse.service',
               configuration: lhsd_data)

install_data(current_build_dir + '/laniakea-lighthouse.service',
             install_dir: systemd_dep.get_pkgconfig_variable('systemdsystemunitdir'))

if (get_option('enable-webgui'))
    sd_data = configuration_data()
    sd_data.set('LKWEB_INSTALL_BIN', get_option('prefix') + '/lib/laniakea/web/laniakea-web')

    configure_file(input: 'laniakea-web.service.in',
                   output: 'laniakea-web.service',
                   configuration: sd_data)

    install_data(current_build_dir + '/laniakea-web.service',
                 install_dir: systemd_dep.get_pkgconfig_variable('systemdsystemunitdir'))
endif
