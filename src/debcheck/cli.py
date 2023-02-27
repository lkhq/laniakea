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
    PackageType,
    ArchiveSuite,
    DebcheckIssue,
    ArchiveRepository,
    ArchiveRepoSuiteSettings,
    session_scope,
)
from laniakea.logging import log

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


def _update_debcheck_issues(session, repo, suite, new_issues, package_type):
    """Refresh the database entries and remove obsolete issues."""
    log.info('Updating issues and discarding old entries for %s/%s', repo.name, suite.name)

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

    # diff new entries against old one and ensure the package type
    # is set correctly, as it sometimes is not explicitly set in Dose reports
    for issue in new_issues:
        issue.package_type = package_type
        stale_issue_uuids.discard(issue.uuid)

    # delete obsolete entries
    for uuid in stale_issue_uuids:
        log.debug('Discarding obsolete issue in %s/%s: %s', repo.name, suite.name, uuid)
        session.query(DebcheckIssue).filter(DebcheckIssue.uuid == uuid).delete()

    # make the result persistent
    session.commit()


def command_sources(options):
    """Check source packages"""

    with session_scope() as session:
        debcheck, repo, scan_suites = _create_debcheck(session, options.repo_name, options.suite)

        for suite in scan_suites:
            log.info('Checking source packages in %s/%s', repo.name, suite.name)
            issues = debcheck.fetch_build_depcheck_issues(suite)
            _update_debcheck_issues(session, repo, suite, issues, PackageType.SOURCE)


def command_binaries(options):
    """Check binary packages"""

    with session_scope() as session:
        debcheck, repo, scan_suites = _create_debcheck(session, options.repo_name, options.suite)

        for suite in scan_suites:
            log.info('Checking binary packages in %s/%s', repo.name, suite.name)
            issues = debcheck.fetch_depcheck_issues(suite)
            _update_debcheck_issues(session, repo, suite, issues, PackageType.BINARY)


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
    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    check_verbose(args)
    args.func(args)
