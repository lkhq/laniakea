# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
import multiprocessing as mp
from argparse import ArgumentParser

from laniakea.db import SynchrotronConfig, session_scope
from laniakea.logging import log

from .syncengine import SyncEngine, SyncSetupError

__mainfile = None


def command_sync(options):
    """Synchronize a dedicated set of packages"""

    if not options.packages:
        print('You need to define at least one package to synchronize!')
        sys.exit(1)

    try:
        engine = SyncEngine(options.repo_name, options.dest_suite, options.src_os, options.src_suite)
    except SyncSetupError as e:
        print('Unable to setup synchronization:', str(e))
        sys.exit(1)

    ret = engine.sync_packages(options.component, options.packages, options.force)
    if not ret:
        sys.exit(2)


def command_autosync(options):
    """Automatically synchronize packages"""

    from laniakea.userhints import UserHints

    uhints = UserHints()
    uhints.load(update=True)
    try:
        uhints.update_synchrotron_blacklists()
    except Exception as e:
        log.error('Failed to import user hints from Git: %s', str(e))

    with session_scope() as session:
        autosyncs_q = (
            session.query(SynchrotronConfig)
            .filter(SynchrotronConfig.sync_enabled == True)  # noqa: E712
            .filter(SynchrotronConfig.sync_auto_enabled == True)  # noqa: E712
        )
        if options.repo_name:
            autosyncs_q = autosyncs_q.filter(SynchrotronConfig.repo.has(name=options.repo_name))
        autosyncs = autosyncs_q.all()

        for autosync in autosyncs:
            try:
                engine = SyncEngine(
                    autosync.repo.name,
                    autosync.destination_suite.name,
                    autosync.source.os_name,
                    autosync.source.suite_name,
                )
            except SyncSetupError as e:
                print('Unable to setup synchronization:', str(e))
                sys.exit(1)

            ret = engine.autosync(autosync.auto_cruft_remove)
            if not ret:
                sys.exit(2)

            # commit pending changes
            session.commit()


def create_parser(formatter_class=None):
    '''Create synchrotron CLI argument parser'''

    parser = ArgumentParser(description='Synchronize packages with another distribution')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose', help='Enable debug messages.')
    parser.add_argument(
        '--version', action='store_true', dest='show_version', help='Display the version of Laniakea itself.'
    )

    sp = subparsers.add_parser('sync', help='Synchronize a package or set of packages')
    sp.add_argument(
        '--force', action='store_true', dest='force', help='Force package import and ignore version conflicts.'
    )
    sp.add_argument('--repo', dest='repo_name', help='Act on the repository with this name.')
    sp.add_argument('src_os', type=str, help='The OS to synchronize from')
    sp.add_argument('src_suite', type=str, help='The suite to synchronize from')
    sp.add_argument('dest_suite', type=str, help='The suite to synchronize to')
    sp.add_argument('component', type=str, help='The archive component to import from')
    sp.add_argument('packages', nargs='+', help='The (source) packages to import')
    sp.set_defaults(func=command_sync)

    sp = subparsers.add_parser(
        'autosync', help='Automatically synchronize all suitable packages for active sync configurations'
    )
    sp.add_argument('--repo', dest='repo_name', help='Act on the repository with this name.')
    sp.set_defaults(func=command_autosync)

    return parser


def check_print_version(options):
    if options.show_version:
        from laniakea import __version__

        print(__version__)
        sys.exit(0)


def check_verbose(options):
    if options.verbose:
        from laniakea.logging import set_verbose

        set_verbose(True)


def run(mainfile, args):
    from laniakea.logging import configure_pkg_archive_logger
    from laniakea.utils.misc import set_process_title, ensure_laniakea_master_user

    set_process_title('synchrotron')
    global __mainfile
    __mainfile = mainfile

    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    # configure multiprocessing
    mp.set_start_method('forkserver', force=True)

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    check_verbose(args)

    ensure_laniakea_master_user(warn_only=True)

    # configure the archive action file logging
    configure_pkg_archive_logger()

    args.func(args)
