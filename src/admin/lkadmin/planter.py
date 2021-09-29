# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
from .utils import print_header, input_str


def ask_settings(options):

    def planter_set_value(key, value):
        from laniakea.db.core import LkModule, config_set_value
        config_set_value(LkModule.PLANTER, key, value)

    print_header('Configuring settings for Planter (metapackages / germinator)')

    git_url = input_str('Git clone URL for the germinate metapackage sources')
    if git_url:
        planter_set_value('git_seeds_url', git_url)


def module_planter_init(options):
    ''' Change the Laniakea Planter module '''

    if options.config:
        ask_settings(options)
    else:
        print('No action selected.')
        sys.exit(1)


def add_cli_parser(parser):
    sp = parser.add_parser('planter', help='Configure settings for Planter (seed packages)')

    sp.add_argument('--config', action='store_true', dest='config',
                    help='Configure this module.')

    sp.set_defaults(func=module_planter_init)
