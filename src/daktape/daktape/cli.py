# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
from argparse import ArgumentParser

__mainfile = None


def check_print_version(options):
    if options.show_version:
        from laniakea import __version__
        print(__version__)
        sys.exit(0)


def create_parser(formatter_class=None):
    ''' Create Daktape CLI argument parser '''

    parser = ArgumentParser(description='Laniakea DAK bridge')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of Laniakea itself.')

    import daktape.admin as admin
    admin.add_cli_parser(subparsers)

    return parser


def run(mainfile, args):
    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    global __mainfile
    __mainfile = mainfile

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    args.func(args)
