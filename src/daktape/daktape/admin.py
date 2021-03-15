# -*- coding: utf-8 -*-
#
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
from laniakea.dakbridge import DakBridge


def run_dak_command(options):
    dak = DakBridge()
    r = dak.run(options.run)
    if r:
        print(r)


def run_add_suite(options):
    dak = DakBridge()

    # pylint: disable=pointless-string-statement
    '''
    dak admin s add-all-arches amber 8 origin=PureOS archive=repo
    dak admin s-c add amber main

    dak admin s add-all-arches amber-debug 8 origin=PureOS archive=repo-debug
    dak admin s-c add amber-debug main

    # adjust overridesuite, debugsuite_id and overridecodename in projectb database

    dak init-dirs
    '''

    dak.run(options.run)


def module_admin_init(options):
    ''' Run DakTape admin actions '''

    if options.run:
        run_dak_command(options)
    else:
        print('No action selected.')
        sys.exit(1)


def add_cli_parser(parser):
    sp = parser.add_parser('admin', help='Run (manual) administrative actions')

    sp.add_argument('--run', nargs='*', dest='run',
                    help='Pass all arguments to the dak CLI tool.')

    sp.set_defaults(func=module_admin_init)
