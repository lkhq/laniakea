# Meson definition for Laniakea Documentation

r = run_command(pymod_check_exe, [pymod_check_arg, 'docs'])
if r.returncode() != 0
    error(r.stderr().strip())
endif

sphinxb_exe = find_program('sphinx-build')
sphinx_apidoc_exe = find_program('sphinx-apidoc')

# maintainer target to generate documentation
run_target ('docs-html',
    command: [sphinxb_exe,
              meson.current_source_dir(),
              join_paths(build_root, 'docs-html'),
              '-b', 'html'
    ]
)

# maintainer target to update API doc templates
run_target ('update-apidoc',
    command: [sphinx_apidoc_exe,
              '-o', join_paths(meson.current_source_dir(), 'api'),
              join_paths(source_root, 'src'),
              '--tocfile', 'index',
              '-H', 'API'
    ]
)
