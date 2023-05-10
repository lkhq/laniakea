#!/usr/bin/env python3
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import sys

thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(thisfile), '..')))

from argparse import ArgumentParser

import laniakea.typing as T
from laniakea import LocalConfig
from laniakea.db import (
    LkModule,
    PackageType,
    ArchiveSuite,
    DebcheckIssue,
    ArchiveRepository,
    ArchiveRepoSuiteSettings,
    session_scope,
)
from laniakea.logging import log
from laniakea.msgstream import EventEmitter

from .dose import DoseDebcheck


def _create_debcheck(session, repo_name: T.Optional[str], suite_name: T.Optional[str]):
    """Create a new Debcheck instance with the given parameters."""

    if not repo_name:
        lconf = LocalConfig()
        repo_name = lconf.master_repo_name
        if not repo_name:
            print('Repository name is not specified, but required.')
            sys.exit(2)

    repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == repo_name).one()

    if suite_name:
        # we only scan a specific suite
        suite = session.query(ArchiveSuite).filter(ArchiveSuite.name == suite_name).one()
        scan_suites = [suite]
    else:
        rss_matches = (
            session.query(ArchiveRepoSuiteSettings)
            .filter(ArchiveRepoSuiteSettings.repo_id == repo.id, ArchiveRepoSuiteSettings.frozen == False)  # noqa: E712
            .all()
        )
        scan_suites = [rss.suite for rss in rss_matches]

    return DoseDebcheck(session, repo), repo, scan_suites


def _cleanup_and_emit_debcheck_issues(
    session,
    repo: ArchiveRepository,
    suite: ArchiveSuite,
    new_issues: list[DebcheckIssue],
    all_issues: list[DebcheckIssue],
    package_type: PackageType,
) -> None:
    """Refresh the database entries and remove obsolete issues."""
    log.info('Emitting issues and discarding old entries for %s/%s', repo.name, suite.name)

    emitter = EventEmitter(LkModule.DEBCHECK)

    def event_data_for_issue(issue: DebcheckIssue):
        event_data = {
            'time_created': issue.time.isoformat(),
            'package_type': PackageType.to_string(issue.package_type),
            'repo': issue.repo.name,
            'suite': issue.suite.name,
            'architectures': issue.architectures,
            'package_name': issue.package_name,
            'package_version': issue.package_version,
        }
        return event_data

    # remove old entries
    res = (
        session.query(DebcheckIssue.uuid)
        .filter(
            DebcheckIssue.package_type == package_type,
            DebcheckIssue.repo_id == repo.id,
            DebcheckIssue.suite_id == suite.id,
        )
        .all()
    )

    stale_issue_uuids = set()
    for e in res:
        stale_issue_uuids.add(e[0])

    stale_issues: list[DebcheckIssue] = []

    # find obsolete entries
    for issue in all_issues:
        stale_issue_uuids.discard(issue.uuid)
    for uuid in stale_issue_uuids:
        stale_issues.append(session.query(DebcheckIssue).filter(DebcheckIssue.uuid == uuid).one())

    # delete obsolete entries
    for stale_issue in stale_issues:
        log.debug(
            'Discarding obsolete issue in %s/%s for %s/%s/%s',
            repo.name,
            suite.name,
            stale_issue.package_type,
            stale_issue.package_name,
            stale_issue.package_version,
        )
        emitter.submit_event('issue-resolved', event_data_for_issue(stale_issue))
        session.delete(stale_issue)

    # emit messages for new issues
    for new_issue in new_issues:
        log.debug(
            'Found new issue in %s/%s for %s/%s/%s',
            repo.name,
            suite.name,
            new_issue.package_type,
            new_issue.package_name,
            new_issue.package_version,
        )
        event_data = event_data_for_issue(new_issue)
        event_data['uuid'] = str(new_issue.uuid)
        emitter.submit_event('issue-found', event_data)

    emitter.submit_event(
        'check-completed',
        {
            'package_type': PackageType.to_string(package_type),
            'repo': repo.name,
            'suite': suite.name,
            'new_issues_count': len(new_issues),
            'resolved_issues_count': len(stale_issues),
        },
    )

    # make the result persistent
    session.commit()


def command_sources(options):
    """Check source packages"""

    with session_scope() as session:
        debcheck, repo, scan_suites = _create_debcheck(session, options.repo_name, options.suite)

        for suite in scan_suites:
            log.info('Checking source packages in %s/%s', repo.name, suite.name)
            new_issues, all_issues = debcheck.fetch_build_depcheck_issues(suite)
            _cleanup_and_emit_debcheck_issues(session, repo, suite, new_issues, all_issues, PackageType.SOURCE)


def command_binaries(options):
    """Check binary packages"""

    with session_scope() as session:
        debcheck, repo, scan_suites = _create_debcheck(session, options.repo_name, options.suite)

        for suite in scan_suites:
            log.info('Checking binary packages in %s/%s', repo.name, suite.name)
            new_issues, all_issues = debcheck.fetch_depcheck_issues(suite)
            _cleanup_and_emit_debcheck_issues(session, repo, suite, new_issues, all_issues, PackageType.BINARY)


def create_parser(formatter_class=None):
    """Create Debcheck CLI argument parser"""

    parser = ArgumentParser(description='Check package dependencies and generate issue reports.')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose', help='Enable debug messages.')
    parser.add_argument(
        '--version', action='store_true', dest='show_version', help='Display the version of Laniakea itself.'
    )

    sp = subparsers.add_parser('binaries', help='Analyze issues in binary packages.')
    sp.add_argument('--repo', dest='repo_name', help='Act only on the repository with this name.')
    sp.add_argument('suite', type=str, help='The suite to check.', nargs='?')
    sp.set_defaults(func=command_binaries)

    sp = subparsers.add_parser('sources', help='Analyze issues in source packages.')
    sp.add_argument('--repo', dest='repo_name', help='Act only on the repository with this name.')
    sp.add_argument('suite', type=str, help='The suite to check.', nargs='?')
    sp.set_defaults(func=command_sources)

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
    from laniakea.utils import set_process_title

    set_process_title('laniakea-debcheck')

    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    check_verbose(args)
    args.func(args)
