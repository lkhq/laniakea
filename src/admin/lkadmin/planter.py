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
from laniakea.db import config_get_value
from argparse import ArgumentParser, HelpFormatter
from .utils import print_header, print_done, print_note, input_str, input_bool, input_list


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
