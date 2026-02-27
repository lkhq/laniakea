
# we only need to fetch JS/CSS/fonts if we are building web frontends
if get_option('webgui')

npm_stage_deps = []
if not fs.is_file('static/bulma/LICENSE')
    npm_exe = find_program('npm')

    npm_stage_deps += custom_target('stage-npm-static',
        output: 'stage-npm-static.stamp',
        command: [
          python,
          source_root / 'vendor' / 'update-static.py',
          '--stamp', '@OUTPUT@',
          'stage',
          '--npm', npm_exe,
        ],
        console: true,
        build_by_default: true,
    )
endif

custom_target('copy-npm-static',
    output: 'copy-npm-static.stamp',
    command: [python,
                source_root / 'vendor' / 'update-static.py',
                '--stamp', '@OUTPUT@',
                'copy'],
    depends: npm_stage_deps,
    build_by_default: true,
)

endif # end of webgui option
