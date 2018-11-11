#!/usr/bin/env python3

import os
import sys

thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(thisfile), '..')))

from argparse import ArgumentParser
from laniakea import LocalConfig
from lknative import BaseConfig, SynchrotronConfig, SyncEngine


def get_sync_config():
    from laniakea.lknative_utils import create_native_baseconfig

    bconf = create_native_baseconfig()
    sconf = SynchrotronConfig()

    # TODO

    return bconf, sconf


def command_sync(options):
    ''' Synchronize a dedicated set of packages '''


    bconf, sconf = get_sync_config()


def command_autosync(options):
    ''' Automatically synchronize packages '''

    pass


def create_parser(formatter_class=None):
    ''' Create synchrotron CLI argument parser '''

    parser = ArgumentParser(description='Synchronize packages with another distribution')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of debspawn itself.')

    sp = subparsers.add_parser('sync', help='Synchronize a package or set of packages')
    sp.set_defaults(func=command_sync)

    sp = subparsers.add_parser('autosync', help='Synchronize a package or set of packages')

    sp.set_defaults(func=command_autosync)

    return parser


def check_print_version(options):
    if options.show_version:
        from laniakea import __version__
        print(__version__)
        sys.exit(0)


def check_verbose(options):
    if options.verbose:
        from laniakea.logging import set_verbose
        set_verbose(True)


def run(args):
    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    args.func(args)

if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
