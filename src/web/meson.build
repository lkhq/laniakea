# Meson config for the web QA frontend

current_src_dir = meson.current_source_dir()

#
# Additional dependencies
#
vibe_http_dep = dependency('vibe-http')
vibe_web_dep  = dependency('vibe-web')

lk_web_tmpl = [
  #  'views/migration/excuse-details.dt',
  #  'views/migration/excuses.dt',
  #  'views/synchrotron/syncoverview.dt'
]

lk_web_src = [
    'app.d',
    'webconfig.d',
    'spearsweb.d',
    'syncweb.d',
    'depcheckweb.d',
    'workersweb.d',
    'isoimagesweb.d',
    'jobsweb.d'
]

lkweb_exe = executable ('laniakea-web',
    [lk_web_src, lk_web_tmpl],
    dependencies: [laniakea_shared_dep,
                   vibe_http_dep,
                   vibe_web_dep],
    d_args: ['-J' + current_src_dir + '/views/', '-d-version=VibeDefaultMain', '-d-version=Have_diet_ng'],
    install: true,
    install_dir: 'lib/laniakea/web/'
)
