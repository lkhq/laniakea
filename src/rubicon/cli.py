# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
from argparse import ArgumentParser

from .fileimport import import_files

__mainfile = None


def check_print_version(options):
    if options.show_version:
        from laniakea import __version__

        print(__version__)
        sys.exit(0)


def create_parser():
    '''Create Rubicon CLI argument parser'''

    parser = ArgumentParser(description='Import artifacts into a secure area')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose', help='Enable debug messages.')
    parser.add_argument(
        '--version', action='store_true', dest='show_version', help='Display the version of Laniakea itself.'
    )
    parser.add_argument(
        '--repo', dest='repo_name', help='Act only on the repository with this name, instead of on all repositories.'
    )
    parser.add_argument(
        'incoming_dir', nargs='?', default=None, help='Override the directory of incoming files to process.'
    )

    return parser


def run(mainfile, args):
    from laniakea.logging import configure_pkg_archive_logger
    from laniakea.utils.misc import set_process_title, ensure_laniakea_master_user

    set_process_title('laniakea-rubicon')
    global __mainfile
    __mainfile = mainfile

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)

    # ensure we run as the correct user
    ensure_laniakea_master_user()
    # configure the archive action file logging
    configure_pkg_archive_logger()

    import_files(args)
