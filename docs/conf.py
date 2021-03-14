# Configuration file for the Sphinx documentation builder.

import os
import sys

# -- Project information -----------------------------------------------------

project = 'Laniakea'
copyright = '2016-2020, Matthias Klumpp'
author = 'Matthias Klumpp'

# The full version, including alpha/beta/rc tags
release = '0.1'

# -- General configuration ---------------------------------------------------
thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(thisfile), '..', 'src')))
on_rtd = os.environ.get('READTHEDOCS') == 'True'

html_theme = 'sphinxawesome_theme'
html_theme_options = {"show_prev_next": True}

extensions = ['sphinx.ext.autodoc',
              'sphinx.ext.coverage',
              'sphinx.ext.intersphinx',
              'sphinx_autodoc_typehints']

if on_rtd:
    autodoc_mock_imports = ['gi', 'systemd', 'apt_pkg']

# Intersphinx
intersphinx_mapping = {'python': ('https://docs.python.org/3', None)}

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']
