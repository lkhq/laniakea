# Meson definition for Laniakea

src_dir = include_directories('.')

#
# Install directories
#
lk_priv_bin_target = 'lib/laniakea/'

#
# Modules
#

# Laniakea core
subdir('laniakea')

# Admin cli tool
if (get_option('cli-admin'))
    subdir('lkadmin')
endif

# Key management cli tool
if (get_option('cli-admin'))
    subdir('keytool')
endif

# Archive management cli tool
subdir('lkarchive')

# Lighthouse relay
if (get_option('lighthouse'))
    subdir('lighthouse')
endif

# Background task scheduler daemon
if (get_option('scheduler'))
    subdir('lkscheduler')
endif

# E-Mail emitter
if (get_option('mailgun'))
    subdir('mailgun')
endif

# Debcheck
if (get_option('debcheck'))
    subdir('debcheck')
endif

# Rubicon data importer
if (get_option('rubicon'))
    subdir('rubicon')
endif

# Planter
if (get_option('planter'))
    subdir('planter')
endif

# Spears
if (get_option('spears'))
    subdir('spears')
endif

# Synchrotron
if (get_option('synchrotron'))
    subdir('synchrotron')
endif

# Ariadne
if (get_option('ariadne'))
    subdir('ariadne')
endif

# mIrk
if (get_option('mirk'))
    subdir('mirk')
endif

# web frontends
if (get_option('webgui'))
    # Additional Python deps
    r = run_command(pymod_check_exe, [pymod_check_arg, 'web'], check: false)
    if r.returncode() != 0
        error(r.stderr().strip())
    endif

    # JS/CSS/etc frontend 3rd-party downloaded code
    if get_option('download-npm')
        npm_exe = find_program('npm')
        if run_command('[', '-f', 'webdash/templates/default/static/css/bulma.min.css', ']', check: false).returncode() != 0
            message('Downloading NPM packages for web frontends...')
            getjs_cmd = run_command(py, source_root + '/contrib/npmdeps/fetch_npm.py', npm_exe, check: false)
            if getjs_cmd.returncode() != 0
                error('Unable to install NPM packages:\n' + getjs_cmd.stdout() + getjs_cmd.stderr())
            endif
        endif
    endif

    # admin & technical overview
    subdir('webdash')
    # software view
    subdir('webswview')
endif
