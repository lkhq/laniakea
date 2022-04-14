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

from laniakea.db import (
    PackageType,
    ArchiveSuite,
    DebcheckIssue,
    ArchiveRepository,
    session_scope,
)
from laniakea.debcheck import Debcheck


def _create_debcheck(session, suite_name):
    # FIXME: Don't hardcode the "master" repository here, fully implement
    # the "multiple repositories" feature
    repo_name = 'master'

    repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == repo_name).one()

    scan_suites = []
    if suite_name:
        # we only scan a specific suite
        suite = session.query(ArchiveSuite).filter(ArchiveSuite.name == suite_name).one()
        scan_suites = [suite]
    else:
        scan_suites = session.query(ArchiveSuite).filter(ArchiveSuite.frozen == False).all()  # noqa: E712

    return Debcheck(repo), repo, scan_suites


def _update_debcheck_issues(session, repo, suite, new_issues, package_type):

    # remove old entries
    for issue in new_issues:
        session.expunge(issue)
    session.query(DebcheckIssue).filter(DebcheckIssue.package_type == package_type).filter(
        DebcheckIssue.repo_id == repo.id
    ).filter(DebcheckIssue.suite_id == suite.id).delete()

    # add new entries
    for issue in new_issues:
        issue.package_type = package_type
        session.add(issue)

    # make the result persistent
    session.commit()


def command_sources(options):
    '''Check source packages'''

    with session_scope() as session:
        debcheck, repo, scan_suites = _create_debcheck(session, options.suite)

        for suite in scan_suites:
            issues = debcheck.build_depcheck_issues(suite)
            _update_debcheck_issues(session, repo, suite, issues, PackageType.SOURCE)


def command_binaries(options):
    '''Check binary packages'''

    with session_scope() as session:
        debcheck, repo, scan_suites = _create_debcheck(session, options.suite)

        for suite in scan_suites:
            issues = debcheck.depcheck_issues(suite)
            _update_debcheck_issues(session, repo, suite, issues, PackageType.BINARY)


def create_parser(formatter_class=None):
    '''Create Debcheck CLI argument parser'''

    parser = ArgumentParser(description='Import existing static data into the Laniakea database')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose', help='Enable debug messages.')
    parser.add_argument(
        '--version', action='store_true', dest='show_version', help='Display the version of Laniakea itself.'
    )

    sp = subparsers.add_parser('binaries', help='Analyze issues in binary packages.')
    sp.add_argument('suite', type=str, help='The suite to check.', nargs='?')
    sp.set_defaults(func=command_binaries)

    sp = subparsers.add_parser('sources', help='Analyze issues in source packages.')
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


def run(args):
    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    check_verbose(args)
    args.func(args)


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
