# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

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
