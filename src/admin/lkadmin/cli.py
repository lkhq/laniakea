# Copyright (C) 2018 Matthias Klumpp <matthias@tenstral.net>
#
# Licensed under the GNU Lesser General Public License Version 3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the license, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import logging as log
from argparse import ArgumentParser, HelpFormatter

__mainfile = None


def check_print_version(options):
    if options.show_version:
        from . import __version__
        print(__version__)
        sys.exit(0)


class CustomArgparseFormatter(HelpFormatter):

    def _split_lines(self, text, width):
        print(text)
        if text.startswith('CF|'):
            return text[3:].splitlines()
        return HelpFormatter._split_lines(self, text, width)


def create_parser(formatter_class=None):
    ''' Create debspawn CLI argument parser '''

    if not formatter_class:
        formatter_class = CustomArgparseFormatter

    parser = ArgumentParser(description='Administer a Laniakea instance', formatter_class=formatter_class)
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of debspawn itself.')

    import lkadmin.core as core
    core.add_cli_parser(subparsers)

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
