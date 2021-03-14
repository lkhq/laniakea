# Meson definition for Laniakea Documentation

r = run_command(pymod_check_exe, [pymod_check_arg, 'docs'])
if r.returncode() != 0
    error(r.stderr().strip())
endif

sphinxb_exe = find_program('sphinx-build')

# maintainer target to update requirements files
run_target ('docs-html',
    command: [sphinxb_exe,
              meson.current_source_dir(),
              join_paths(build_root, 'docs-html'),
              '-b', 'html'
    ]
)
