# Copyright (C) 2018-2019 Matthias Klumpp <matthias@tenstral.net>
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
from .fileimport import import_files

__mainfile = None


def check_print_version(options):
    if options.show_version:
        from laniakea import __version__
        print(__version__)
        sys.exit(0)


def create_parser():
    ''' Create Rubicon CLI argument parser '''

    parser = ArgumentParser(description='Import artifacts into a secure area')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of Laniakea itself.')
    parser.add_argument('incoming_dir', nargs='?', default=None,
                        help='The directory of incoming files to process.')

    return parser


def run(mainfile, args):
    global __mainfile
    __mainfile = mainfile

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    import_files(args)
