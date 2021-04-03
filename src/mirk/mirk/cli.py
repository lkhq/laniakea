# -*- coding: utf-8 -*-
#
# Copyright (C) 2019-2021 Matthias Klumpp <matthias@tenstral.net>
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
import asyncio
from argparse import ArgumentParser
from .msgpublish import MatrixPublisher


def run_matrix_bot(options):
    if options.verbose:
        from laniakea.logging import set_verbose
        set_verbose(True)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot_pub = MatrixPublisher()
    try:
        loop.run_until_complete(bot_pub.run())
    finally:
        bot_pub.stop()
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


def check_print_version(options):
    if options.show_version:
        from laniakea import __version__
        print(__version__)
        sys.exit(0)


def create_parser():
    ''' Create mIrk CLI argument parser '''

    parser = ArgumentParser(description='Matrix message bot')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of Laniakea itself.')

    parser.set_defaults(func=run_matrix_bot)

    return parser


def run(mainfile, args):
    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    args.func(args)
