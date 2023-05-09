# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
from argparse import ArgumentParser

__mainfile = None


def run_server(options):
    from laniakea.logging import set_verbose
    from laniakea.utils.misc import ensure_laniakea_master_user
    from lkscheduler.sdaemon import SchedulerDaemon
    from laniakea.localconfig import LocalConfig

    set_verbose(options.verbose)
    if options.config_fname:
        LocalConfig(options.config_fname)

    # we must run as the designated master user, otherwise we might run into permission error
    # or, even worse, create security risks in case we run as root
    ensure_laniakea_master_user(warn_only=options.no_user_check)

    daemon = SchedulerDaemon()
    daemon.run()


def check_print_version(options):
    if options.show_version:
        from laniakea import __version__

        print(__version__)
        sys.exit(0)


def create_parser():
    """Create Laniakea Scheduler CLI argument parser"""

    parser = ArgumentParser(description='Archive management task scheduler')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose', help='Enable debug messages.')
    parser.add_argument(
        '--version', action='store_true', dest='show_version', help='Display the version of Laniakea itself.'
    )
    parser.add_argument(
        '--no-user-check',
        action='store_true',
        dest='no_user_check',
        help='Don\'t verify that we run as the right user.',
    )
    parser.add_argument(
        '--config',
        action='store',
        dest='config_fname',
        default=None,
        help='Location of the base configuration file to use.',
    )

    parser.set_defaults(func=run_server)

    return parser


def run(mainfile, args):
    from laniakea.utils import set_process_title

    set_process_title('laniakea-scheduler')
    global __mainfile
    __mainfile = mainfile

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    args.func(args)
