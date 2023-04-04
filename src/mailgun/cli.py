# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
import asyncio
from argparse import ArgumentParser

from .mailrelay import MailRelay

__mainfile = None


def run_relay(options):
    from laniakea.localconfig import LocalConfig

    if options.config_fname:
        LocalConfig(options.config_fname)

    if options.verbose:
        from laniakea.logging import set_verbose

        set_verbose(True)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    relay = MailRelay()
    try:
        loop.run_until_complete(relay.run())
    finally:
        relay.stop()
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


def check_print_version(options):
    if options.show_version:
        from laniakea import __version__

        print(__version__)
        sys.exit(0)


def create_parser():
    """Create Laniakea Mailgun argument parser"""

    parser = ArgumentParser(description='E-Mail emitter')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose', help='Enable debug messages.')
    parser.add_argument(
        '--version', action='store_true', dest='show_version', help='Display the version of Laniakea itself.'
    )
    parser.add_argument(
        '--config',
        action='store',
        dest='config_fname',
        default=None,
        help='Location of the base configuration file to use.',
    )

    parser.set_defaults(func=run_relay)

    return parser


def run(mainfile, args):
    from laniakea.utils import set_process_title

    set_process_title('laniakea-mailgun')
    global __mainfile
    __mainfile = mainfile

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    args.func(args)
