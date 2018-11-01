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
from argparse import ArgumentParser, HelpFormatter

__mainfile = None


def database_init(options):
    from laniakea.db import Database, session_factory
    db = Database()
    db.create_tables()


def module_core_init(options):
    ''' Change the Laniakea Core module '''

    if options.init_db:
        database_init(options)
    else:
        print('No action selected.')
        sys.exit(1)


def add_cli_parser(parser):
    sp = parser.add_parser('core', help='Basic actions that affect all modules')

    sp.add_argument('--init-db', action='store_true', dest='init_db',
                    help='Initialize database tables.')
    sp.set_defaults(func=module_core_init)
