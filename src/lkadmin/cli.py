# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
from argparse import ArgumentParser, HelpFormatter

__mainfile = None


def check_print_version(options):
    if options.show_version:
        from laniakea import __version__
        print(__version__)
        sys.exit(0)


class CustomArgparseFormatter(HelpFormatter):

    def _split_lines(self, text, width):
        print(text)
        if text.startswith('CF|'):
            return text[3:].splitlines()
        return HelpFormatter._split_lines(self, text, width)


def create_parser(formatter_class=None):
    ''' Create lkadmin CLI argument parser '''

    if not formatter_class:
        formatter_class = CustomArgparseFormatter

    parser = ArgumentParser(description='Administer a Laniakea instance', formatter_class=formatter_class)
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of Laniakea itself.')

    import lkadmin.core as core
    core.add_cli_parser(subparsers)

    import lkadmin.job as job
    job.add_cli_parser(subparsers)

    import lkadmin.synchrotron as synchrotron
    synchrotron.add_cli_parser(subparsers)

    import lkadmin.spears as spears
    spears.add_cli_parser(subparsers)

    import lkadmin.ariadne as ariadne
    ariadne.add_cli_parser(subparsers)

    import lkadmin.isotope as isotope
    isotope.add_cli_parser(subparsers)

    import lkadmin.planter as planter
    planter.add_cli_parser(subparsers)

    import lkadmin.flatpak as flatpak
    flatpak.add_cli_parser(subparsers)

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
