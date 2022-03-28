# -*- coding: utf-8 -*-
#
# Copyright (C) 2021-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys

import rich
import click
from rich.table import Table
from rich.console import Console

import laniakea.typing as T
from laniakea import LocalConfig
from laniakea.db import (
    NewPolicy,
    BinaryPackage,
    SourcePackage,
    ArchiveRepository,
    ArchiveRepoSuiteSettings,
    session_scope,
)


@click.command('ls')
@click.option(
    '--repo',
    'repo_name',
    default=None,
    help='Name of the repository to act on, if not set all repositories will be checked',
)
@click.option(
    '--suite',
    '-s',
    'suite_name',
    default=None,
    help='Name of the suite to act on, if not set all suites will be processed',
)
@click.argument('term', nargs=1)
def list(term: str, repo_name: T.Optional[str], suite_name: T.Optional[str]):
    """List repository packages."""

    term_q = '%' + term + '%'
    with session_scope() as session:
        # find source packages
        spkg_q = session.query(SourcePackage).filter(SourcePackage.name.like(term_q))
        if repo_name:
            spkg_q = spkg_q.filter(SourcePackage.repo.has(name=repo_name))
        if suite_name:
            spkg_q = spkg_q.filter(SourcePackage.suite.has(name=suite_name))
        spkgs = spkg_q.all()

        # find binary packages
        bpkg_q = session.query(BinaryPackage).filter(BinaryPackage.name.like(term_q))
        if repo_name:
            bpkg_q = spkg_q.filter(BinaryPackage.repo.has(name=repo_name))
        if suite_name:
            bpkg_q = spkg_q.filter(BinaryPackage.suite.has(name=suite_name))
        bpkgs = bpkg_q.all()

        if not spkgs and not bpkgs:
            click.echo('Nothing found.', err=True)
            sys.exit(2)

        table = Table(box=rich.box.MINIMAL)
        table.add_column('Package', no_wrap=True)
        table.add_column('Version', style='magenta', no_wrap=True)
        table.add_column('Repository')
        table.add_column('Suites')
        table.add_column('Component')
        table.add_column('Architectures')

        for spkg in spkgs:
            table.add_row(
                spkg.name,
                spkg.version,
                spkg.repo.name,
                ' '.join([s.name for s in spkg.suites]),
                spkg.component.name,
                'source',
            )
        for bpkg in bpkgs:
            table.add_row(
                bpkg.name,
                bpkg.version,
                bpkg.repo.name,
                ' '.join([s.name for s in bpkg.suites]),
                bpkg.component.name,
                bpkg.architecture.name,
            )

        console = Console()
        console.print(table)
