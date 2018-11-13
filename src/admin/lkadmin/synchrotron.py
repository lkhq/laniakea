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
from laniakea.db import session_factory
from argparse import ArgumentParser, HelpFormatter
from .utils import print_header, print_done, print_note, input_str, input_bool, input_list


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
        suite['components'] = input_list('List of components for suite \'{}\''.format (suite['name']))
        suite['architectures'] = input_list('List of architectures for suite \'{}\''.format (suite['name']))

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


def module_synchrotron_init(options):
    ''' Change the Laniakea Synchrotron module '''

    if options.config:
        ask_settings(options)
    else:
        print('No action selected.')
        sys.exit(1)


def add_cli_parser(parser):
    sp = parser.add_parser('synchrotron', help='Basic actions that affect all modules')

    sp.add_argument('--config', action='store_true', dest='config',
                    help='Configure this module.')

    sp.set_defaults(func=module_synchrotron_init)
