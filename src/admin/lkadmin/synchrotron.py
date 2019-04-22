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

import sys
from .utils import print_header, print_note, input_str, input_bool, input_list
from laniakea.db import session_scope, SyncBlacklistEntry


def ask_settings(options):

    def syncconf_set_value(key, value):
        from laniakea.db.core import LkModule, config_set_value
        config_set_value(LkModule.SYNCHROTRON, key, value)

    print_header('Configuring base settings for Synchrotron')

    syncconf_set_value('source_name', input_str('Name of the source distribution'))
    syncconf_set_value('source_repo_url', input_str('Source repository URL'))

    add_suite = True
    suites = {}
    while add_suite:
        suite = {}

        suite['name'] = input_str('Adding a new source suite. Please set a name')
        suite['components'] = input_list('List of components for suite \'{}\''.format(suite['name']))
        suite['architectures'] = input_list('List of architectures for suite \'{}\''.format(suite['name']))

        suites[suite['name']] = suite
        add_suite = input_bool('Add another suite?')

    syncconf_set_value('source_suites', list(suites.values()))
    while True:
        default_suite_name = input_str('Default source suite')
        if default_suite_name in suites:
            syncconf_set_value('source_default_suite', default_suite_name)
            break
        print_note('Selected default suite not found in previously defined suites list.')

    syncconf_set_value('sync_enabled', input_bool('Enable synchronization?'))
    syncconf_set_value('sync_binaries', input_bool('Synchronize binary packages?'))


def add_blacklist_entry(pkgname, reason):
    with session_scope() as session:
        # delete existing entry in case it exists
        entry = session.query(SyncBlacklistEntry).filter(SyncBlacklistEntry.pkgname == pkgname).one_or_none()
        if entry:
            print_note('Updating existing entry for this package.')
        else:
            entry = SyncBlacklistEntry()
            session.add(entry)
        entry.pkgname = pkgname
        entry.reason = reason


def remove_blacklist_entry(pkgname):
    with session_scope() as session:
        # delete existing entry in case it exists
        entry = session.query(SyncBlacklistEntry).filter(SyncBlacklistEntry.pkgname == pkgname).one_or_none()
        if entry:
            session.delete(entry)
        else:
            print_note('The selected package was not in blacklist. Nothing was removed.')


def module_synchrotron_init(options):
    ''' Change the Laniakea Synchrotron module '''

    if options.config:
        ask_settings(options)
    elif options.blacklist_add:
        info = options.blacklist_add
        if len(info) != 2:
            print('Needs a package name and a reason string as paremeters.')
        add_blacklist_entry(info[0], info[1])
    elif options.blacklist_remove:
        remove_blacklist_entry(options.blacklist_remove)
    else:
        print('No action selected.')
        sys.exit(1)


def add_cli_parser(parser):
    sp = parser.add_parser('synchrotron', help='Adjust package synchronization settings.')

    sp.add_argument('--config', action='store_true', dest='config',
                    help='Configure this module.')
    sp.add_argument('--blacklist-add', nargs='+', dest='blacklist_add',
                    help='Blacklist a package from automatic sync. Takes package name as first, and reason as second parameter.')
    sp.add_argument('--blacklist-remove', dest='blacklist_remove',
                    help='Remove a package from the sync blacklist.')

    sp.set_defaults(func=module_synchrotron_init)
