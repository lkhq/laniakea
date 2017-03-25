# Meson config for the web QA frontend

current_src_dir = meson.current_source_dir()

#
# Additional dependencies
#
vibe_http_dep = dependency('vibe-http')
vibe_web_dep  = dependency('vibe-web')
vibe_diet_dep = dependency('vibe-diet')

lk_web_src = [
    'app.d',
    'spearsweb.d',
    'webconfig.d',
    '/usr/include/d/vibe/appmain.d'
]

lkadmin_exe = executable ('laniakea-web',
    [lk_web_src],
    include_directories: [src_dir],
    link_with: [laniakea_lib],
    dependencies: [base_deps,
                   vibe_http_dep,
                   vibe_web_dep,
                   vibe_diet_dep],
    d_args: ['-J' + current_src_dir + '/views/', '-d-version=VibeDefaultMain'],
    install: true,
    install_dir: 'lib/laniakea/web/'
)
