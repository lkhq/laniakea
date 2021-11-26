# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

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
    '''Run DakTape admin actions'''

    if options.run:
        run_dak_command(options)
    else:
        print('No action selected.')
        sys.exit(1)


def add_cli_parser(parser):
    sp = parser.add_parser('admin', help='Run (manual) administrative actions')

    sp.add_argument('--run', nargs='*', dest='run', help='Pass all arguments to the dak CLI tool.')

    sp.set_defaults(func=module_admin_init)
