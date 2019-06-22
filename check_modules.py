#!/usr/bin/env python3
#
# Check whether all required Python modules are found on the system.
#

import os
import sys
import subprocess

thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
os.chdir(os.path.normpath(os.path.join(os.path.dirname(thisfile))))


def get_installed_modules():
    pip_freeze = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'])
    installed_modules = [e.decode().split('==')[0] for e in pip_freeze.split()]
    return set(installed_modules)


def ensure_modules(modules):
    all_modules = get_installed_modules()

    for mod_name in modules:
        if mod_name not in all_modules:
            print('Unable to find Python module: {}'.format(mod_name))
            sys.exit(2)


def ensure_gir():
    import gi

    try:
        gi.require_version('AppStream', '1.0')
        from gi.repository import AppStream  # noqa
    except ValueError:
        print('Laniakea requires AppStream GObject introspection data. Please install it to continue.')
        sys.exit(2)


def ensure_modules_by_group(group_name):
    with open('requirements.{}.txt'.format(group_name), 'r') as f:
        modules = [e.strip().split('==')[0] for e in f.readlines()]

        ensure_modules(modules)
        if group_name == 'base':
            ensure_gir()


def ensure_python():
    if sys.version_info[0] < 3 or sys.version_info[1] < 6:
        print('Laniakea requires at least Python 3.6 to run!')
        sys.exit(2)


def run(args):
    group_name = None
    if len(args) > 0:
        group_name = args[0]
    if not group_name:
        print('No group name set to check modules for!')
        sys.exit(1)
    ensure_python()

    ensure_modules_by_group(group_name)
    return 0


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
