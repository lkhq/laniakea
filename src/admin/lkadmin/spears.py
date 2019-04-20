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

import sys
from laniakea.db import session_factory
from .utils import print_header, input_str, input_bool, input_list, \
    input_int, print_error_exit


def ask_settings(options):
    from laniakea.db import SpearsMigrationEntry, VersionPriority

    print_header('Configuring settings for Spears (migrations)')

    session = session_factory()

    add_migration = True
    while add_migration:
        entry = SpearsMigrationEntry()

        entry.source_suites = input_list('Migrate from suites (source names)')
        entry.target_suite = input_str('Migrate to suite (target name)')

        entry.delays = {}
        for prio in VersionPriority:
            entry.delays[int(prio)] = input_int('Delay for packages of priority "{}" in days'.format(repr(prio)))

        # FIXME: We need to check for uniqueness of the migration task!
        entry.idname = entry.make_migration_id()
        session.add(entry)
        session.commit()

        add_migration = input_bool('Add another migration task?')


def add_hint(options):
    from laniakea.db import SpearsHint

    if not options.source_suite:
        print_error_exit('The source-suite parameter is missing!')
    if not options.target_suite:
        print_error_exit('The target-suite parameter is missing!')
    if not options.hint:
        print_error_exit('The hint parameter is missing!')
    if not options.reason:
        print_error_exit('The reason parameter is missing!')

    session = session_factory()

    migration_id = '{}-to-{}'.format(options.source_suite, options.target_suite)

    # remove a preexisting hint
    session.query(SpearsHint) \
        .filter(SpearsHint.migration_id == migration_id, SpearsHint.hint == options.hint) \
        .delete()

    hint = SpearsHint()
    hint.migration_id = migration_id
    hint.hint = options.hint
    hint.reason = options.reason

    session.add(hint)
    session.commit()


def remove_hint(options):
    from laniakea.db import SpearsHint

    if not options.source_suite:
        print_error_exit('The source-suite parameter is missing!')
    if not options.target_suite:
        print_error_exit('The target-suite parameter is missing!')
    if not options.hint:
        print_error_exit('The hint parameter is missing!')

    session = session_factory()

    migration_id = '{}-to-{}'.format(options.source_suite, options.target_suite)
    session.query(SpearsHint) \
        .filter(SpearsHint.migration_id == migration_id, SpearsHint.hint == options.hint) \
        .delete()


def module_spears_init(options):
    ''' Change the Laniakea Spears module '''

    if options.config:
        ask_settings(options)
    elif options.add_hint:
        add_hint(options)
    elif options.remove_hint:
        remove_hint(options)
    else:
        print('No action selected.')
        sys.exit(1)


def add_cli_parser(parser):
    sp = parser.add_parser('spears', help='Configure automatic package migration.')

    sp.add_argument('--config', action='store_true', dest='config',
                    help='Configure this module.')

    sp.add_argument('--add-hint', action='store_true', dest='add_hint',
                    help='Add a migration hint.')
    sp.add_argument('--remove-hint', action='store_true', dest='add_hint',
                    help='Remove a migration hint.')
    sp.add_argument('source_suite', action='store', nargs='?', default=None,
                    help='The source suite(s) for the hint.')
    sp.add_argument('target_suite', action='store', nargs='?', default=None,
                    help='The target suite for the hint.')
    sp.add_argument('hint', action='store', nargs='?', default=None,
                    help='A britney hint.')
    sp.add_argument('reason', action='store', nargs='?', default=None,
                    help='The reason for adding the printey hint.')

    sp.set_defaults(func=module_spears_init)
