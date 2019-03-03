#!/usr/bin/env python3
#
# Copyright (C) 2016-2019 Matthias Klumpp <matthias@tenstral.net>
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

import os
import sys

thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(thisfile), '..')))

from argparse import ArgumentParser
from laniakea import LocalConfig, LkModule
from laniakea.db import session_factory, ArchiveSuite, ArchiveArchitecture, ArchiveRepository, \
    PackageType, DebcheckIssue, PackageIssue, PackageConflict


def _create_debcheck(session, suite_name):
    from lknative import Debcheck
    from laniakea.lknative_utils import create_native_baseconfig, \
        get_suiteinfo_all_suites, get_suiteinfo_for_suite

    bconf = create_native_baseconfig()

    scan_suites = []
    if suite_name:
        # we only scan a specific suite
        suite = session.query(ArchiveSuite) \
            .filter(ArchiveSuite.name==suite_name).one()
        scan_suites = [get_suiteinfo_for_suite(suite)]
    else:
        scan_suites = get_suiteinfo_all_suites()

    return Debcheck(bconf), scan_suites


def _native_issue_to_package_issue(m):
    mpi = PackageIssue()

    mpi.package_type = m.packageKind
    mpi.package_name = m.packageName
    mpi.packageVersion = m.packageVersion
    mpi.architecture = m.architecture

    mpi.depends = m.depends
    mpi.unsat_dependency = m.unsatDependency
    mpi.unsat_conflict = m.unsatConflict

    return mpi


def _update_debcheck_issues(session, repo, si, new_issues, package_type):

    suite = session.query(ArchiveSuite) \
        .filter(ArchiveSuite.name==si.name).one()

    # remove old entries
    x = session.query(DebcheckIssue) \
        .filter(DebcheckIssue.package_type==package_type) \
        .filter(DebcheckIssue.repo_id==repo.id) \
        .filter(DebcheckIssue.suite_id==suite.id).delete()

    # add new entries
    for ni in new_issues:
        issue = DebcheckIssue()
        #issue.time = ni.date # FIXME: crashes in PyD at the moment

        issue.package_type = ni.packageKind
        issue.repo = repo
        issue.suite = suite
        issue.architecture = ni.architecture

        issue.package_name = ni.packageName
        issue.package_version = ni.packageVersion

        missing = list()
        for m in ni.missing:
            missing.append(_native_issue_to_package_issue(m))
        issue.set_issues_missing(missing)

        conflicts = list()
        for c in ni.conflicts:
            pc = PackageConflict()
            pc.pkg1 = _native_issue_to_package_issue(c.pkg1)
            pc.pkg2 = _native_issue_to_package_issue(c.pkg2)

            pc.depchain1 = [_native_issue_to_package_issue(npi) for npi in c.depchain1]
            pc.depchain2 = [_native_issue_to_package_issue(npi) for npi in c.depchain2]
            conflicts.append(pc)
        issue.set_issues_conflicts(conflicts)

        session.add(issue)

    # make the result persistent
    session.commit()


def command_sources(options):
    ''' Check source packages '''

    session = session_factory()
    debcheck, scan_suites = _create_debcheck(session, options.suite)

    # FIXME: Don't hardcode the "master" repository here, fully implement
    # the "multiple repositories" feature
    repo_name = 'master'
    repo = session.query(ArchiveRepository) \
        .filter(ArchiveRepository.name==repo_name).one()

    for si in scan_suites:
        ret, issues = debcheck.getBuildDepCheckIssues(si)
        _update_debcheck_issues(session, repo, si, issues, PackageType.SOURCE)


def command_binaries(options):
    ''' Check binary packages '''

    session = session_factory()
    debcheck, scan_suites = _create_debcheck(session, options.suite)

    # FIXME: Don't hardcode the "master" repository here, fully implement
    # the "multiple repositories" feature
    repo_name = 'master'
    repo = session.query(ArchiveRepository) \
        .filter(ArchiveRepository.name==repo_name).one()

    for si in scan_suites:
        ret, issues = debcheck.getDepCheckIssues(si)
        _update_debcheck_issues(session, repo, si, issues, PackageType.BINARY)


def create_parser(formatter_class=None):
    ''' Create DataImport CLI argument parser '''

    parser = ArgumentParser(description='Import existing static data into the Laniakea database')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of debspawn itself.')

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
