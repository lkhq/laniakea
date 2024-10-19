# -*- coding: utf-8 -*-
#
# Copyright (C) 2021-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import sys
from datetime import datetime
from dataclasses import field, dataclass

import rich
import click
from rich import print
from pebble import ProcessPool
from apt_pkg import Hashes
from rich.panel import Panel
from rich.table import Table
from rich.console import Console
from sqlalchemy.orm import selectinload

import laniakea.typing as T
from laniakea.db import (
    ArchiveFile,
    BinaryPackage,
    SourcePackage,
    ArchiveSection,
    PackageOverride,
    ArchiveRepository,
    ArchiveQueueNewEntry,
    session_scope,
)
from laniakea.logging import log, archive_log


@dataclass
class IssueReport:
    title: str
    issues: list[T.Tuple[str, str]] = field(default_factory=list)
    issues_fixed: list[T.Tuple[str, str]] = field(default_factory=list)


def _ensure_package_consistency(session, repo: ArchiveRepository, fix_issues: bool = True) -> list[IssueReport]:
    """Ensure binary and source package suite associations match, and we have no orphaned packages."""

    log.info('Detecting suite mismatches between binary and source packages for %s', repo.name)
    issues_fixed = []
    issues = []

    log.debug('Retrieving source packages')
    spkgs = (
        session.query(SourcePackage)
        .options(selectinload(SourcePackage.files), selectinload(SourcePackage.binaries))
        .filter(SourcePackage.repo_id == repo.id, SourcePackage.time_deleted.is_(None))
        .yield_per(1000)
    )
    queue_spkg_q = (
        session.query(ArchiveQueueNewEntry.package_uuid)
        .filter(
            ArchiveQueueNewEntry.package.has(repo_id=repo.id),
        )
        .all()
    )
    queue_spkg_uuids = set()
    for e in queue_spkg_q:
        queue_spkg_uuids.add(e[0])
    del queue_spkg_q

    log.debug('Verifying source packages')
    for spkg in spkgs:
        if not spkg.suites:
            if spkg.uuid in queue_spkg_uuids:
                continue  # skip packages in NEW queue
            else:
                issues_fixed.append(('{}/{}/source'.format(spkg.name, spkg.version), 'No suites'))
                if fix_issues:
                    spkg.time_deleted = datetime.utcnow()
                    archive_log.info('%s: %s/%s @ %s', 'MARKED-REMOVAL-SRC', spkg.name, spkg.version, repo.name)
                    for bpkg in spkg.binaries:
                        bpkg.time_deleted = datetime.utcnow()
                        archive_log.info('MARKED-REMOVAL-BIN: %s/%s @ %s', bpkg.name, bpkg.version, repo.name)
                continue

        # check that the source package is in a suite along with its binaries
        for bin in spkg.binaries:
            if bin.time_deleted:
                # we ignore deleted binary packages
                continue

            for suite in bin.suites:
                # handle the debug-suite special case for binary -> source
                if bin.repo.is_debug:
                    if suite.debug_suite_for:
                        suite = suite.debug_suite_for
                    else:
                        # we skip this check in case we don't have a matching suite
                        continue

                # check
                if suite not in spkg.suites:
                    issues_fixed.append(
                        (
                            '{}/{}/source'.format(spkg.name, spkg.version),
                            'Missing suite: {} (via {})'.format(suite.name, bin.name),
                        )
                    )
                    if fix_issues:
                        spkg.suites.append(suite)
                        log.debug('FIX: Add suite %s to %s/%s/source', suite.name, spkg.name, spkg.version)

        if not spkg.files:
            issues.append(('{}/{}/source'.format(spkg.name, spkg.version), 'No files'))

    # free some memory
    del spkgs

    log.info('Finding orphaned binaries and missing overrides for %s', repo.name)
    log.debug('Retrieving binary packages')
    bpkgs = (
        session.query(BinaryPackage)
        .options(selectinload(BinaryPackage.source), selectinload(BinaryPackage.architecture))
        .filter(BinaryPackage.repo_id == repo.id, BinaryPackage.time_deleted.is_(None))
        .yield_per(1000)
    )

    log.debug('Verifying binary packages')
    debug_section = session.query(ArchiveSection).filter(ArchiveSection.name == 'debug').one()
    for bpkg in bpkgs:
        if not bpkg.source:
            issues.append(('{}/{}/{}'.format(bpkg.name, bpkg.version, bpkg.architecture.name), 'No source package'))
        if not bpkg.component:
            issues.append(('{}/{}/{}'.format(bpkg.name, bpkg.version, bpkg.architecture.name), 'No component'))

        for suite in bpkg.suites:
            e_ov = (
                session.query(PackageOverride)
                .filter(
                    PackageOverride.repo_id == bpkg.repo_id,
                    PackageOverride.suite_id == suite.id,
                    PackageOverride.pkg_name == bpkg.name,
                )
                .first()
            )

            # skip already existing overrides
            if e_ov:
                if not e_ov.component:
                    issues_fixed.append(
                        (
                            '{}/{}/{}'.format(bpkg.name, bpkg.version, bpkg.architecture.name),
                            'Override has no component',
                        )
                    )
                    if fix_issues:
                        e_ov.component = bpkg.component
                if not e_ov.section:
                    issues_fixed.append(
                        (
                            '{}/{}/{}'.format(bpkg.name, bpkg.version, bpkg.architecture.name),
                            'Override has no section',
                        )
                    )
                    if fix_issues:
                        e_ov.section = debug_section if bpkg.repo.is_debug else bpkg.source.section
                continue

            # override is missing
            issues_fixed.append(
                (
                    '{}/{}/{}'.format(bpkg.name, bpkg.version, bpkg.architecture.name),
                    'Override missing',
                )
            )

            if fix_issues:
                other_ov = (
                    session.query(PackageOverride)
                    .filter(
                        PackageOverride.repo_id == bpkg.repo_id,
                        PackageOverride.pkg_name == bpkg.name,
                    )
                    .first()
                )
                log.debug('FIX: Add new override for %s/%s/%s', bpkg.name, bpkg.version, bpkg.architecture.name)
                ov = PackageOverride(bpkg.name, bpkg.repo, suite)
                ov.pkg_name = bpkg.name
                if other_ov:
                    ov.essential = other_ov.essential
                    ov.component = other_ov.component
                    ov.section = other_ov.section
                    ov.priority = other_ov.priority
                else:
                    ov.essential = False
                    ov.component = bpkg.component
                    ov.section = debug_section if bpkg.repo.is_debug else bpkg.source.section
                session.add(ov)

    del bpkgs

    report = IssueReport('Package Consistency')
    if fix_issues:
        report.issues_fixed = issues_fixed
    else:
        issues.extend(issues_fixed)
    report.issues = issues
    return [report]


def _verify_hashes(
    file: ArchiveFile, repo_root_dir: T.PathUnion, repo_new_queue_dir: T.PathUnion
) -> T.Optional[T.Tuple[str, str]]:
    """Verifies all known hashes of the archive file."""

    local_fname = os.path.join(repo_root_dir, file.fname)
    if not os.path.isfile(local_fname):
        local_fname = os.path.join(repo_new_queue_dir, file.fname)
        if not os.path.isfile(local_fname):
            return (file.fname, 'Missing file (expected {})'.format(local_fname))

    with open(local_fname, 'rb') as f:
        # pylint: disable=not-an-iterable
        for hash in Hashes(f).hashes:  # type: ignore
            hash_okay = False
            if hash.hashtype == 'MD5Sum':
                hash_okay = file.md5sum == hash.hashvalue
            elif hash.hashtype == 'SHA1':
                hash_okay = file.sha1sum == hash.hashvalue
            elif hash.hashtype == 'SHA256':
                hash_okay = file.sha256sum == hash.hashvalue
            elif hash.hashtype == 'SHA512':
                if file.sha512sum is not None:
                    hash_okay = file.sha512sum == hash.hashvalue
            elif hash.hashtype == 'Checksum-FileSize':
                hash_okay = int(file.size) == int(hash.hashvalue)
            else:
                raise Exception(
                    'Unknown hash type "{}" - Laniakea likely needs to be adjusted to a new APT version.'.format(
                        hash.hashtype
                    )
                )
            if not hash_okay:
                return (file.fname, 'Bad {} checksum (expected {})'.format(hash.hashtype, hash.hashvalue))
    return None


def _verify_files(session, repo: ArchiveRepository) -> list[IssueReport]:
    """verify file checksums"""

    log.info('Verifying file checksums for %s', repo.name)

    log.debug('Retrieving all files from database')
    afiles = (
        session.query(ArchiveFile)
        .options(selectinload(ArchiveFile.pkgs_source), selectinload(ArchiveFile.pkg_binary))
        .filter(ArchiveFile.repo_id == repo.id)
        .yield_per(1000)
    )

    repo_root = repo.get_root_dir()
    repo_new_queue_root = repo.get_new_queue_dir()
    known_files: set[str] = set()

    log.debug('Verifying hashes')
    hash_report = IssueReport('Hash verification')
    with ProcessPool() as pool:
        futures = []
        for file in afiles:
            known_files.add(file.fname)
            futures.append(pool.schedule(_verify_hashes, args=(file, repo_root, repo_new_queue_root), timeout=15 * 60))

        for future in futures:
            r = future.result()
            if r:
                hash_report.issues.append(r)

    del afiles

    log.debug('Finding local files with no database equivalent')
    lfile_report = IssueReport('Local File Consistency')
    for path, _, files in os.walk(repo_root):
        for file in files:
            fname = os.path.relpath(os.path.join(path, file), repo_root)
            if fname.startswith('dists/') or fname.startswith('zzz-meta/'):
                continue
            if fname not in known_files:
                lfile_report.issues.append((fname, 'Local file has no database entry'))

    return [hash_report, lfile_report]


@click.command('check-integrity')
@click.option(
    '--repo',
    'repo_name',
    default=None,
    help='Name of the repository to act on, if not set all repositories will be checked',
)
@click.option('--fix/--no-fix', 'fix_issues', default=False, help='Attempt to fix some of the found issues')
@click.option(
    '--verify-files/--no-verify-files', 'verify_files', default=True, help='Verify file integrity, locations and hashes'
)
def check_integrity(repo_name: T.Optional[str], fix_issues: bool, verify_files: bool = True):
    """Verify database and file integrity & consistency."""

    with session_scope() as session:
        if repo_name:
            repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == repo_name).one_or_none()
            if not repo:
                click.echo('Unable to find repository with name {}!'.format(repo_name), err=True)
                sys.exit(1)
            repos = [repo]
        else:
            repos = session.query(ArchiveRepository).all()

        console = Console()
        if fix_issues:
            print(':warning: Will attempt to fix issues, if possible.')
        else:
            print(':warning: Will NOT attempt to fix issues.')

        with console.status("[bold green]Working..."):
            repo_reports = {}
            for repo in repos:
                res = []
                res.extend(_ensure_package_consistency(session, repo, fix_issues))
                if verify_files:
                    res.extend(_verify_files(session, repo))
                repo_reports[repo.name] = res

                # commit any changes
                if fix_issues:
                    session.commit()

        def print_report_table(title, issues):
            table = Table(box=rich.box.MINIMAL, title=title)
            table.add_column('Entity', no_wrap=True)
            table.add_column('Issue')

            for issue in issues:
                table.add_row(issue[0], issue[1])
            console.print(table)

        summary = {}
        print(Panel('Issue Report'))
        print()

        for repo_name, reports in repo_reports.items():
            print(Panel.fit('Issues in {}'.format(repo_name)))
            issue_count = 0
            for report in reports:
                if report.issues_fixed:
                    print_report_table(
                        '{}: {} (automatically fixed)'.format(repo_name, report.title), report.issues_fixed
                    )
                    issue_count += len(report.issues_fixed)
                if report.issues:
                    print_report_table('{}: {}'.format(repo_name, report.title), report.issues)
                    issue_count += len(report.issues)
            summary[repo_name] = issue_count
            if issue_count == 0:
                print('  • No issues')

    print()
    print(Panel.fit('Summary'))
    failed = False
    for repo_name, issue_count in summary.items():
        if issue_count > 0:
            print('[bold red]✘[/bold red] Found [red]{} errors[/red] in repository {}'.format(issue_count, repo_name))
            failed = True
        else:
            print('[bold green]✔[/bold green] No problems in repository {}'.format(repo_name))

    if failed:
        sys.exit(5)
