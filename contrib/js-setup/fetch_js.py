#!/usr/bin/env python3
#
# Retrieve web packages via Yarn and move them to the right locations.
#

import os
import sys
import subprocess
import shutil
from glob import glob

thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
thisdir = os.path.normpath(os.path.join(os.path.dirname(thisfile)))
os.chdir(thisdir)


src_dir = '../../src/'
node_modules = [{'name': 'bootstrap',
                 'files': ['dist/css/bootstrap.min.css', 'dist/css/bootstrap.min.css.map',
                           'dist/js/bootstrap.min.js', 'dist/js/bootstrap.min.js.map'],
                 'copy_to': [os.path.join(src_dir, 'web/static/bootstrap/'),
                             os.path.join(src_dir, 'webswview/templates/default/static/bootstrap/')]
                 },

                {'name': '@fortawesome/fontawesome-free',
                 'files': ['css/fontawesome.min.css', 'css/all.min.css'],
                 'copy_to': [os.path.join(src_dir, 'web/static/css/fontawesome/'),
                             os.path.join(src_dir, 'webswview/templates/default/static/css/fontawesome/')]
                 },

                {'name': '@fortawesome/fontawesome-free',
                 'files': ['webfonts/*'],
                 'copy_to': [os.path.join(src_dir, 'web/static/css/webfonts/'),
                             os.path.join(src_dir, 'webswview/templates/default/static/css/webfonts/')]
                 },

                {'name': 'jquery',
                 'files': ['dist/jquery.slim.min.js'],
                 'copy_to': [os.path.join(src_dir, 'web/static/js/jquery/'),
                             os.path.join(src_dir, 'webswview/templates/default/static/js/jquery/')]
                 },

                {'name': 'popper.js',
                 'files': ['dist/*.min.js'],
                 'copy_to': [os.path.join(src_dir, 'web/static/js/popper/'),
                             os.path.join(src_dir, 'webswview/templates/default/static/js/popper/')]
                 }

                ]


def fetch_node_modules():
    subprocess.run(['yarn',
                    'install',
                    # '--no-bin-links',  # Disabled, as for some reason not all Yarn versions recognize this
                    '--prod',
                    '--no-lockfile',
                    '--non-interactive'], check=True)


def install_node_modules():
    for info in node_modules:
        mod_dir = os.path.join(thisdir, 'node_modules', info['name'])
        install_dests = [os.path.normpath(os.path.join(thisdir, d)) for d in info['copy_to']]
        for pattern in info['files']:
            matches = [m for m in glob(os.path.join(mod_dir, pattern))]
            if not matches:
                print('Could not find any match for {}'.format(pattern), file=sys.stderr)
                sys.exit(1)
            for fname in matches:
                for dest in install_dests:
                    os.makedirs(dest, exist_ok=True)
                    shutil.copy(fname, dest)


def run(args):
    fetch_node_modules()
    install_node_modules()
    return 0


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
