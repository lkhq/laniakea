# -*- coding: utf-8 -*-
#
# Copyright (C) 2021-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import sys
import shutil

import rich
import click
from rich.table import Table
from rich.prompt import Prompt
from rich.console import Console

import laniakea.typing as T
from laniakea.db import (
    PackageInfo,
    SourcePackage,
    PackagePriority,
    ArchiveQueueNewEntry,
    ArchiveRepoSuiteSettings,
    session_scope,
)
from laniakea.archive import PackageImporter
from laniakea.logging import archive_log
from laniakea.archive.utils import (
    check_overrides_source,
    find_package_in_new_queue,
    register_package_overrides,
)
from laniakea.archive.changes import parse_changes


def newqueue_accept(
    session,
    rss: ArchiveRepoSuiteSettings,
    spkg: SourcePackage,
    overrides: T.List[PackageInfo],
    *,
    include_binaries: bool = False,
):
    """Accept a selected package into its target suite, applying the selected overrides"""
    from glob import glob

    dsc_file = spkg.dsc_file
    if not dsc_file:
        raise ValueError('Source package {}/{} has no registered dsc file.'.format(spkg.name, spkg.version))

    register_package_overrides(session, rss, overrides)
    session.commit()
    spkg_queue_dir = os.path.join(rss.repo.get_new_queue_dir(), spkg.directory)
    spkg_fname = os.path.join(rss.repo.get_new_queue_dir(), dsc_file.fname)
    pi = PackageImporter(session, rss)
    pi.import_source(spkg_fname, spkg.component.name, error_if_new=True)
    session.commit()

    if include_binaries:
        for bpkg_fname in glob(os.path.join(spkg_queue_dir, '*.deb')):
            pi.import_binary(bpkg_fname)
        for bpkg_fname in glob(os.path.join(spkg_queue_dir, '*.udeb')):
            pi.import_binary(bpkg_fname)
    shutil.rmtree(spkg_queue_dir)
    archive_log.info(
        'ACCEPTED: %s/%s -> %s/%s/%s', spkg.name, spkg.version, rss.repo.name, rss.suite.name, spkg.component.name
    )


def newqueue_reject(session, rss: ArchiveRepoSuiteSettings, spkg: SourcePackage):
    """Reject a selected package from the NEW queue"""

    dsc_file = spkg.dsc_file
    if not dsc_file:
        raise ValueError('Source package {}/{} has no registered dsc file.'.format(spkg.name, spkg.version))

    # TODO: Don't completely delete the package and maybe just move it to the morgue
    spkg_queue_dir = os.path.join(rss.repo.get_new_queue_dir(), spkg.directory)

    nq_entry = find_package_in_new_queue(session, rss, spkg)
    if not nq_entry:
        raise ValueError('Unable to find NEW queue entry for package {}/{}!'.format(spkg.name, spkg.version))

    shutil.rmtree(spkg_queue_dir)
    session.delete(nq_entry)
    for file in spkg.files:
        session.delete(file)
    spkg.files = []
    session.delete(spkg)
    session.flush()
    archive_log.info(
        'REJECTED: %s/%s (aimed at %s/%s/%s)',
        spkg.name,
        spkg.version,
        rss.repo.name,
        rss.suite.name,
        spkg.component.name,
    )


def _process_new(repo_name: T.Optional[str] = None):
    console = Console()
    with session_scope() as session:
        if repo_name:
            repo_suites = (
                session.query(ArchiveRepoSuiteSettings).filter(ArchiveRepoSuiteSettings.repo.has(name=repo_name)).all()
            )
            if not repo_suites:
                click.echo('Unable to find suites in repository {}!'.format(repo_name), err=True)
                sys.exit(1)
        else:
            # we process NEW in all repositories if no filter was set
            repo_suites = session.query(ArchiveRepoSuiteSettings).all()

        for rss in repo_suites:
            queue_entries = (
                session.query(ArchiveQueueNewEntry)
                .filter(
                    ArchiveQueueNewEntry.destination_id == rss.suite_id,
                    ArchiveQueueNewEntry.package.has(repo_id=rss.repo_id),
                )
                .all()
            )

            if not queue_entries:
                click.echo('Nothing in NEW for {} in {}.'.format(rss.suite.name, rss.repo.name))
                continue

            for entry in queue_entries:
                spkg = entry.package

                changes_fname = os.path.join(
                    rss.repo.get_new_queue_dir(), spkg.directory, '{}_{}.changes'.format(spkg.name, spkg.version)
                )
                changes_found = os.path.isfile(changes_fname)
                changes = None
                if changes_found:
                    changes = parse_changes(changes_fname, require_signature=False)

                rich.print('[bold]Package:[/bold]', spkg.name)
                rich.print('[bold]Version:[/bold]', spkg.version)
                rich.print('[bold]Repository:[/bold]', spkg.repo.name)
                rich.print('[bold]Target Suite:[/bold] [italic]{}[/italic]'.format(entry.destination.name))
                rich.print('[bold]Target Component:[/bold] [italic]{}[/italic]'.format(spkg.component.name))
                rich.print('[bold]Maintainer:[/bold]', spkg.maintainer)
                if spkg.uploaders:
                    rich.print('[bold]Uploaders:[/bold]', [u for u in spkg.uploaders])
                if changes_found:
                    rich.print('[bold]Changed By:[/bold]', changes.changes['Changed-By'])
                rich.print('[bold]New Overrides:[/bold]')

                missing_overrides = check_overrides_source(session, rss, spkg)
                table = Table(box=rich.box.MINIMAL)
                table.add_column('Package')
                table.add_column('Section')
                table.add_column('Priority')
                table.add_column('Essential')
                for override in missing_overrides:
                    table.add_row(
                        override.name,
                        override.section
                        if override.component == 'main'
                        else override.component + '/' + override.section,
                        PackagePriority.to_string(override.priority),
                        '[bold red]yes[/bold red]' if override.essential else 'no',
                    )
                console.print(table)
                if not changes_found:
                    rich.print('[orange1]No changes file found for this upload![/orange1]')
                choice = Prompt.ask(
                    'Accept and add the overrides?', choices=['accept', 'reject', 'skip'], default='skip'
                )

                # TODO: Allow user to edit overrides and to send a reject message
                if choice == 'skip':
                    rich.print()
                    continue
                elif choice == 'accept':
                    newqueue_accept(session, rss, spkg, missing_overrides)
                    rich.print(
                        '[green]ACCEPTED[/green] {} {} -> {}'.format(spkg.name, spkg.version, entry.destination.name)
                    )
                elif choice == 'reject':
                    newqueue_reject(session, rss, spkg)
                    rich.print('[red]REJECTED[/red] {} {}'.format(spkg.name, spkg.version))
                rich.print()


@click.command()
@click.option(
    '--repo',
    'repo_name',
    default=None,
    help='Name of the repository to act on, if not set all repositories will be checked',
)
def process_new(repo_name: T.Optional[str] = None):
    """Interactively process source packages in the new packages queue."""

    _process_new(repo_name)
