# -*- coding: utf-8 -*-
#
# Copyright (C) 2021-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+


import sys

import rich
import click
from rich.table import Table
from rich.prompt import Prompt
from rich.console import Console

import laniakea.typing as T
from laniakea import LocalConfig
from laniakea.db import (
    PackageInfo,
    SourcePackage,
    PackagePriority,
    ArchiveQueueNewEntry,
    ArchiveRepoSuiteSettings,
    session_scope,
)
from laniakea.archive.utils import check_overrides_source, register_package_overrides


def _process_new(repo_name: T.Optional[str] = None):
    if not repo_name:
        lconf = LocalConfig()
        repo_name = lconf.master_repo_name

    console = Console()
    with session_scope() as session:
        repo_suites = (
            session.query(ArchiveRepoSuiteSettings).filter(ArchiveRepoSuiteSettings.repo.has(name=repo_name)).all()
        )
        if not repo_suites:
            click.echo('Unable to find suites in repository {}!'.format(repo_name), err=True)
            sys.exit(1)

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
                click.echo('Nothing in NEW for {} in {}.'.format(rss.suite.name, repo_name))
                continue

            for entry in queue_entries:
                spkg = entry.package
                rich.print('[bold]Package:[/bold]', spkg.name)
                rich.print('[bold]Version:[/bold]', spkg.version)
                rich.print('[bold]Repository:[/bold]', spkg.repo.name)
                rich.print('[bold]Target Suite:[/bold] [italic]{}[/italic]'.format(entry.destination.name))
                rich.print('[bold]Target Component:[/bold] [italic]{}[/italic]'.format(spkg.component.name))
                rich.print('[bold]Maintainer:[/bold]', spkg.maintainer)
                if spkg.uploaders:
                    rich.print('[bold]Uploaders:[/bold]', [u for u in spkg.uploaders])
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
                        override.section,
                        PackagePriority.to_string(override.priority),
                        '[bold red]yes[/bold red]' if override.essential else 'no',
                    )
                console.print(table)
                choice = Prompt.ask(
                    'Accept and add the overrides?', choices=['accept', 'reject', 'skip'], default='skip'
                )
                if choice == 'skip':
                    rich.print()
                    continue


def newqueue_accept(session, rss: ArchiveRepoSuiteSettings, spkg: SourcePackage, overrides: T.List[PackageInfo]):
    register_package_overrides(session, rss, overrides)


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
