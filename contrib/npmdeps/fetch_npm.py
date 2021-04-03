#!/usr/bin/env python3
#
# Retrieve web packages via NPM and move them to the right locations.
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
node_modules = [{'name': 'bulma',
                 'files': ['css/bulma.min.css'],
                 'copy_to': [os.path.join(src_dir, 'web/static/css/'),
                             os.path.join(src_dir, 'webswview/templates/default/static/css/'),
                             os.path.join(src_dir, 'webswview/templates/pureos/static/css/')]
                 },

                {'name': '@fortawesome/fontawesome-free',
                 'files': ['css/fontawesome.min.css', 'css/all.min.css'],
                 'copy_to': [os.path.join(src_dir, 'web/static/css/fontawesome/'),
                             os.path.join(src_dir, 'webswview/templates/default/static/css/fontawesome/'),
                             os.path.join(src_dir, 'webswview/templates/pureos/static/css/fontawesome/')]
                 },

                {'name': '@fortawesome/fontawesome-free',
                 'files': ['webfonts/*'],
                 'copy_to': [os.path.join(src_dir, 'web/static/css/webfonts/'),
                             os.path.join(src_dir, 'webswview/templates/default/static/css/webfonts/'),
                             os.path.join(src_dir, 'webswview/templates/pureos/static/css/webfonts/')]
                 },

                {'name': '@fontsource/cantarell',
                 'files': ['files/*'],
                 'copy_to': [os.path.join(src_dir, 'web/static/fonts/'),
                             os.path.join(src_dir, 'webswview/templates/default/static/fonts/'),
                             os.path.join(src_dir, 'webswview/templates/pureos/static/fonts/')]
                 },

                {'name': 'jquery',
                 'files': ['dist/jquery.slim.min.js'],
                 'copy_to': [os.path.join(src_dir, 'web/static/js/jquery/'),
                             os.path.join(src_dir, 'webswview/templates/default/static/js/jquery/'),
                             os.path.join(src_dir, 'webswview/templates/default/static/js/jquery/'),
                             os.path.join(src_dir, 'webswview/templates/pureos/static/js/jquery/')]
                 },
                ]


def fetch_node_modules(node_cmd):
    subprocess.run([node_cmd,
                    'install',
                    '--no-save'], check=True)


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
    if len(args) != 1:
        print('Invalid number of arguments!')
        sys.exit(1)
    fetch_node_modules(args[0])
    install_node_modules()
    return 0


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
