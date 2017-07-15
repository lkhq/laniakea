# Meson config for the web software view frontend

current_src_dir = meson.current_source_dir()

#
# Additional dependencies
#
vibe_http_dep = dependency('vibe-http')
vibe_web_dep  = dependency('vibe-web')
vibe_diet_dep = dependency('vibe-diet')

lk_swview_src = [
    'app.d',
    'webconfig.d',
    'swindex.d',
    'pkgview.d',
    '/usr/include/d/vibe/appmain.d'
]

lkswview_exe = executable ('laniakea-web-swview',
    [lk_swview_src],
    include_directories: [src_dir],
    link_with: [laniakea_lib],
    dependencies: [base_deps,
                   vibe_http_dep,
                   vibe_web_dep,
                   vibe_diet_dep],
    d_args: ['-J' + current_src_dir + '/views/', '-d-version=VibeDefaultMain'],
    install: true,
    install_dir: 'lib/laniakea/web-swview/'
)
