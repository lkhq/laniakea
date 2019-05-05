#!/usr/bin/env python3
#
# Check whether all required Python modules are found on the system.
#

import sys


modules_base = ['sqlalchemy',
                'psycopg2',
                'debian',
                'zmq',
                'yaml',
                'firehose',
                'humanize',
                'marshmallow',
                'tornado',
                'gi']


modules_web = ['flask',
               'flask_script',
               'flask_restful']


def ensure_modules(modules):
    from importlib import util

    for mod_name in modules:
        spec = util.find_spec(mod_name)
        if not spec:
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


def ensure_python():
    if sys.version_info[0] < 3 or sys.version_info[1] < 6:
        print('Laniakea requires at least Python 3.6 to run!')
        sys.exit(2)


def run(args):
    set_name = None
    if len(args) > 0:
        set_name = args[0]
    ensure_python()

    if set_name == 'web':
        ensure_modules(modules_web)
    else:
        ensure_modules(modules_base)
        ensure_gir()

    return 0


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
