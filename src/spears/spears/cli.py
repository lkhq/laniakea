# Copyright (C) 2018-2020 Matthias Klumpp <matthias@tenstral.net>
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

import sys
from argparse import ArgumentParser
from .spearsengine import SpearsEngine

__mainfile = None


def check_print_version(options):
    if options.show_version:
        from laniakea import __version__
        print(__version__)
        sys.exit(0)


def check_verbose(options):
    if options.verbose:
        from laniakea.logging import set_verbose
        set_verbose(True)


def command_update(options):
    ''' Update Britney and its configuration '''

    engine = SpearsEngine()

    ret = engine.update_config()
    if not ret:
        sys.exit(2)


def command_migrate(options):
    ''' Run a Britney migration '''

    engine = SpearsEngine()

    ret = engine.run_migration(options.suite1, options.suite2)
    if not ret:
        sys.exit(2)


def create_parser():
    ''' Create Spears CLI argument parser '''

    parser = ArgumentParser(description='Migrate packages between suites')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of Laniakea itself.')

    sp = subparsers.add_parser('update', help='Update the copy of Britney and its configuration.')
    sp.set_defaults(func=command_update)

    sp = subparsers.add_parser('migrate', help='Run migration. If suites are omitted, migration is run for all targets.')
    sp.add_argument('suite1', type=str, help='The first suite.', nargs='?')
    sp.add_argument('suite2', type=str, help='The second suite.', nargs='?')
    sp.set_defaults(func=command_migrate)

    return parser


def run(mainfile, args):
    global __mainfile
    __mainfile = mainfile

    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    check_verbose(args)
    args.func(args)
