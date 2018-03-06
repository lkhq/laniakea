# Meson config for the web software view frontend

current_src_dir = meson.current_source_dir()

#
# Additional dependencies
#
vibe_http_dep = dependency('vibe-http')
vibe_web_dep  = dependency('vibe-web')

lk_swview_src = [
    'app.d',
    'webconfig.d',
    'swindex.d',
    'pkgview.d',
    'buildsview.d'
]

lkswview_exe = executable ('laniakea-web-swview',
    [lk_swview_src],
    dependencies: [laniakea_shared_dep,
                   vibe_http_dep,
                   vibe_web_dep],
    d_args: ['-J' + current_src_dir + '/views/', '-d-version=VibeDefaultMain', '-d-version=Have_diet_ng'],
    install: true,
    install_dir: 'lib/laniakea/web/'
)
