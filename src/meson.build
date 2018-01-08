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
subdir('c')
subdir('laniakea')

# Admin cli tool
subdir('admin')

# Key management cli tool
subdir('keytool')

# Lighthouse relay
#! subdir('lighthouse')

# Dataimport
#! subdir('dataimport')

# Debcheck
#! subdir('debcheck')

# Rubicon data importer
#! subdir('rubicon')

# Planter
if (get_option('planter'))
    #! subdir('planter')
endif

# Spears
if (get_option('spears'))
    #! subdir('spears')
endif

# Synchrotron
if (get_option('synchrotron'))
    #! subdir('synchrotron')
endif

# web frontends
if (get_option('webgui'))
    # admin & technical overview
    #! subdir('web')
    # software view
    #! subdir('webswview')
endif
