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
subdir('lighthouse')

# Datasync
#! subdir('datasync')

# Debcheck
subdir('debcheck')

# Rubicon data importer
subdir('rubicon')

# Eggshell
if (get_option('enable-eggshell'))
    subdir('eggshell')
endif

# Spears
if (get_option('enable-spears'))
    subdir('spears')
endif

# Synchrotron
if (get_option('enable-synchrotron'))
    subdir('synchrotron')
endif

# web frontends
if (get_option('enable-webgui'))
    # admin & technical overview
    subdir('web')
    # software view
    #! subdir('webswview')
endif
