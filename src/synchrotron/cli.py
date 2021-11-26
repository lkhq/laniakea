# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
from argparse import ArgumentParser

from laniakea import LkModule
from laniakea.db import (
    SynchrotronIssue,
    SynchrotronConfig,
    SynchrotronSource,
    session_scope,
)
from laniakea.logging import log
from laniakea.msgstream import EventEmitter

from .syncengine import SyncEngine

__mainfile = None


def command_sync(options):
    '''Synchronize a dedicated set of packages'''

    if not options.packages:
        print('You need to define at least one package to synchronize!')
        sys.exit(1)

    engine = SyncEngine(options.dest_suite, options.src_suite)
    ret = engine.sync_packages(options.component, options.packages, options.force)
    if not ret:
        sys.exit(2)


def command_autosync(options):
    '''Automatically synchronize packages'''

    with session_scope() as session:
        sync_sources = session.query(SynchrotronSource).all()
        autosyncs = (
            session.query(SynchrotronConfig)
            .filter(SynchrotronConfig.sync_enabled == True)
            .filter(SynchrotronConfig.sync_auto_enabled == True)
            .all()
        )  # noqa: E712

        for autosync in autosyncs:
            log.info(
                'Synchronizing packages from {}/{} with {}'.format(
                    autosync.source.os_name, autosync.source.suite_name, autosync.destination_suite.name
                )
            )

            emitter = EventEmitter(LkModule.SYNCHROTRON)

            engine = SyncEngine(autosync.destination_suite.name, autosync.source.suite_name)
            ret, issue_data = engine.autosync(session, autosync, autosync.auto_cruft_remove)
            if not ret:
                sys.exit(2)
                return

            existing_sync_issues = {}
            for ssource in sync_sources:
                all_issues = (
                    session.query(SynchrotronIssue)
                    .filter(
                        SynchrotronIssue.source_suite == ssource.suite_name,
                        SynchrotronIssue.target_suite == autosync.destination_suite.name,
                        SynchrotronIssue.config_id == autosync.id,
                    )
                    .all()
                )
                for eissue in all_issues:
                    eid = '{}-{}-{}:{}'.format(
                        eissue.package_name, eissue.source_version, eissue.target_version, str(eissue.kind)
                    )
                    existing_sync_issues[eid] = eissue

            for info in issue_data:
                eid = '{}-{}-{}:{}'.format(info.package_name, info.source_version, info.target_version, str(info.kind))
                issue = existing_sync_issues.pop(eid, None)
                if issue:
                    # the issue already exists, so we just update it
                    new_issue = False
                else:
                    new_issue = True
                    issue = info
                    issue.config = autosync

                if new_issue:
                    session.add(issue)

                    data = {
                        'name': issue.package_name,
                        'src_os': autosync.source.os_name,
                        'suite_src': issue.source_suite,
                        'suite_dest': issue.target_suite,
                        'version_src': issue.source_version,
                        'version_dest': issue.target_version,
                        'kind': str(issue.kind),
                    }

                    emitter.submit_event('new-autosync-issue', data)

            for eissue in existing_sync_issues.values():
                session.delete(eissue)

                data = {
                    'name': eissue.package_name,
                    'src_os': autosync.source.os_name,
                    'suite_src': eissue.source_suite,
                    'suite_dest': eissue.target_suite,
                    'version_src': eissue.source_version,
                    'version_dest': eissue.target_version,
                    'kind': str(eissue.kind),
                }

                emitter.submit_event('resolved-autosync-issue', data)


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
    sp.add_argument('src_suite', type=str, help='The suite to synchronize from')
    sp.add_argument('dest_suite', type=str, help='The suite to synchronize to')
    sp.add_argument('component', type=str, help='The archive component to import from')
    sp.add_argument('packages', nargs='+', help='The (source) packages to import')
    sp.set_defaults(func=command_sync)

    sp = subparsers.add_parser('autosync', help='Synchronize a package or set of packages')
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
    global __mainfile
    __mainfile = mainfile

    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    check_verbose(args)
    args.func(args)
