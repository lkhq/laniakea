# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
from .utils import print_header, print_note, input_str


def ask_settings(options):

    def ariadne_set_value(key, value):
        from laniakea.db.core import LkModule, config_set_value
        config_set_value(LkModule.ARIADNE, key, value)

    print_header('Configuring settings for Ariadne (package building)')

    arch_affinity = None
    while not arch_affinity:
        arch_affinity = input_str('Architecture affinity for arch:all / arch-indep packages')
        arch_affinity = arch_affinity.strip() if arch_affinity else None
        if arch_affinity == 'all':
            print_note('Architecture affinity for arch:all can not be arch:all as well.')
            arch_affinity = None

    ariadne_set_value('indep_arch_affinity', arch_affinity)


def module_ariadne_init(options):
    ''' Change the Laniakea Ariadne module '''

    if options.config:
        ask_settings(options)
    else:
        print('No action selected.')
        sys.exit(1)


def add_cli_parser(parser):
    sp = parser.add_parser('ariadne', help='Adjust package builder settings.')

    sp.add_argument('--config', action='store_true', dest='config',
                    help='Configure this module.')

    sp.set_defaults(func=module_ariadne_init)
