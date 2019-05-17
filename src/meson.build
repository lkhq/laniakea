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
subdir('lkshared')
subdir('laniakea')

# Admin cli tool
if (get_option('clitools'))
    subdir('admin')
endif

# Key management cli tool
if (get_option('clitools'))
    subdir('keytool')
endif

# Lighthouse relay
if (get_option('lighthouse'))
    subdir('lighthouse')
endif

# Dataimport
if (get_option('dataimport'))
    subdir('dataimport')
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

# web frontends
if (get_option('webgui'))
    # Additional Python deps
    r = run_command('../check_modules.py', 'web')
    if r.returncode() != 0
        message(r.stdout().strip()+'\n'+r.stderr().strip())
        error('Unable to find required Python modules.')
    endif

    # admin & technical overview
    subdir('web')
    # software view
    subdir('webswview')
endif
