
current_build_dir = meson.current_build_dir()
lk_data_dir = join_paths(get_option('datadir'), 'laniakea')

if get_option('lighthouse')
    lhsd_data = configuration_data()
    lhsd_data.set('LIGHTHOUSE_INSTALL_BIN', get_option('prefix') + '/lib/laniakea/lighthouse/lighthouse-server')

    configure_file(input: 'laniakea-lighthouse.service.in',
                output: 'laniakea-lighthouse.service',
                configuration: lhsd_data)

    install_data(current_build_dir + '/laniakea-lighthouse.service',
                install_dir: systemd_dep.get_pkgconfig_variable('systemdsystemunitdir'))
endif

if get_option('scheduler')
    lksd_data = configuration_data()
    lksd_data.set('SCHEDULER_INSTALL_BIN', get_option('prefix') + '/lib/laniakea/lkscheduler/laniakea-scheduler')

    configure_file(input: 'laniakea-scheduler.service.in',
                output: 'laniakea-scheduler.service',
                configuration: lksd_data)

    install_data(current_build_dir + '/laniakea-scheduler.service',
                install_dir: systemd_dep.get_pkgconfig_variable('systemdsystemunitdir'))
endif

if get_option('webgui')
    sd_data = configuration_data()
    sd_data.set('LKWEB_INSTALL_DIR', get_option('prefix') + '/lib/laniakea/webdash/')
    sd_data.set('LKSWWEB_INSTALL_DIR', get_option('prefix') + '/lib/laniakea/webswview/')

    configure_file(input: 'laniakea-webdash.service.in',
                   output: 'laniakea-webdash.service',
                   configuration: sd_data)

    configure_file(input: 'laniakea-webswview.service.in',
                   output: 'laniakea-webswview.service',
                   configuration: sd_data)

    install_data(current_build_dir + '/laniakea-webdash.service',
                 install_dir: systemd_dep.get_pkgconfig_variable('systemdsystemunitdir'))

    install_data(current_build_dir + '/laniakea-webswview.service',
                 install_dir: systemd_dep.get_pkgconfig_variable('systemdsystemunitdir'))
endif

if get_option('rubicon')
    sd_data = configuration_data()
    sd_data.set('LKUPLOAD_INSTALL_DIR', get_option('prefix') + '/lib/laniakea/webupload/')

    configure_file(input: 'laniakea-webupload.service.in',
                   output: 'laniakea-webupload.service',
                   configuration: sd_data)
    install_data(current_build_dir + '/laniakea-webupload.service',
                 install_dir: systemd_dep.get_pkgconfig_variable('systemdsystemunitdir'))
endif

if get_option('mirk')
    mirk_data = configuration_data()
    mirk_data.set('MIRK_INSTALL_BIN', get_option('prefix') + '/lib/laniakea/mirk/mirk')

    configure_file(input: 'laniakea-mirk.service.in',
                   output: 'laniakea-mirk.service',
                   configuration: mirk_data)

    install_data(current_build_dir + '/laniakea-mirk.service',
                 install_dir: systemd_dep.get_pkgconfig_variable('systemdsystemunitdir'))
endif

config_default_files = [
    '3rd-party.toml',
    'lintian.toml',
]
install_data(config_default_files, install_dir: lk_data_dir)
install_data('archive-sections.json', install_dir: lk_data_dir)
