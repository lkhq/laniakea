# -*- coding: utf-8 -*-
#
# Copyright (C) 2021-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys

import rich
import click
from rich.table import Table
from rich.prompt import Confirm
from rich.console import Console

import laniakea.typing as T
from laniakea import LocalConfig
from laniakea.db import (
    BinaryPackage,
    SourcePackage,
    ArchiveRepoSuiteSettings,
    session_scope,
)
from laniakea.archive import (
    remove_source_package,
    repo_suite_settings_for,
    find_latest_source_package,
)
from laniakea.archive.manage import expire_superseded, copy_source_package


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

    term_q = term.replace('*', '%')
    with session_scope() as session:
        # find source packages
        spkg_q = session.query(SourcePackage).filter(SourcePackage.name.like(term_q))
        if repo_name:
            spkg_q = spkg_q.filter(SourcePackage.repo.has(name=repo_name))
        if suite_name:
            spkg_q = spkg_q.filter(SourcePackage.suite.has(name=suite_name))
        spkgs = spkg_q.order_by(SourcePackage.name.desc(), SourcePackage.version.desc()).all()

        # find binary packages
        bpkg_q = session.query(BinaryPackage).filter(BinaryPackage.name.like(term_q))
        if repo_name:
            bpkg_q = spkg_q.filter(BinaryPackage.repo.has(name=repo_name))
        if suite_name:
            bpkg_q = spkg_q.filter(BinaryPackage.suite.has(name=suite_name))
        bpkgs = bpkg_q.order_by(BinaryPackage.name.desc(), BinaryPackage.version.desc()).all()

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

        bpkg_by_arch: T.Dict[str, T.Any] = {}
        for bpkg in bpkgs:
            bpkid = '{}:{}/{}-{}'.format(bpkg.repo.name, bpkg.component.name, bpkg.name, bpkg.version)
            if bpkid in bpkg_by_arch:
                bpkg_by_arch[bpkid]['archs'].add(bpkg.architecture.name)
                bpkg_by_arch[bpkid]['suites'].update([s.name for s in bpkg.suites])
            else:
                bpkg_by_arch[bpkid] = dict(
                    bpkg=bpkg, archs={bpkg.architecture.name}, suites=set([s.name for s in bpkg.suites])
                )

        for data in bpkg_by_arch.values():
            bpkg = data['bpkg']
            table.add_row(
                bpkg.name,
                bpkg.version,
                bpkg.repo.name,
                ' '.join(data['suites']),
                bpkg.component.name,
                ' '.join(data['archs']),
            )

        console = Console()
        console.print(table)


def print_package_details(spkgs: T.List[SourcePackage]):
    table = Table(box=rich.box.MINIMAL)
    table.add_column('Package', no_wrap=True)
    table.add_column('Version', style='magenta', no_wrap=True)
    table.add_column('Repository')
    table.add_column('Suites')
    table.add_column('Component')
    table.add_column('Binaries')

    for spkg in spkgs:
        table.add_row(
            spkg.name,
            spkg.version,
            spkg.repo.name,
            ' '.join([s.name for s in spkg.suites]),
            spkg.component.name,
            ' '.join([b.name for b in spkg.binaries]),
        )

    console = Console()
    console.print(table)


@click.command('remove')
@click.option(
    '--repo',
    'repo_name',
    default=None,
    help='Name of the repository to act on, if not set the default repository will be used.',
)
@click.option(
    '--suite',
    '-s',
    'suite_name',
    required=True,
    help='Name of the suite to act on.',
)
@click.argument('source_pkgname', nargs=1)
def remove(source_pkgname: str, repo_name: T.Optional[str], suite_name: str):
    """Delete a source package (and its binaries) from a suite in a repository."""

    if not repo_name:
        lconf = LocalConfig()
        repo_name = lconf.master_repo_name

    with session_scope() as session:
        rss = (
            session.query(ArchiveRepoSuiteSettings)
            .filter(
                ArchiveRepoSuiteSettings.repo.has(name=repo_name), ArchiveRepoSuiteSettings.suite.has(name=suite_name)
            )
            .one_or_none()
        )

        if not rss:
            click.echo('Suite {} not found in repository {}.'.format(suite_name, repo_name), err=True)
            sys.exit(2)

        spkgs = (
            session.query(SourcePackage)
            .filter(
                SourcePackage.repo_id == rss.repo_id,
                SourcePackage.suites.any(id=rss.suite_id),
                SourcePackage.name == source_pkgname,
            )
            .all()
        )

        if not spkgs:
            click.echo('Package {} not found in repository {}/{}.'.format(source_pkgname, repo_name, suite_name))
            sys.exit(0)

        print_package_details(spkgs)
        remove_confirmed = Confirm.ask('Do you really want to delete these packages?', default=False)

        if remove_confirmed:
            for spkg in spkgs:
                remove_source_package(session, rss, spkg)


@click.command()
@click.option(
    '--repo',
    'repo_name',
    default=None,
    help='Name of the repository to act on, if not set all repositories will be checked.',
)
def expire(repo_name: T.Optional[str] = None):
    """Expire old package versions and delete them from the archive."""

    with session_scope() as session:
        if repo_name:
            repo_suite = (
                session.query(ArchiveRepoSuiteSettings)
                .filter(ArchiveRepoSuiteSettings.repo.has(name=repo_name))
                .one_or_none()
            )
            if not repo_suite:
                click.echo('Unable to find suites for repository with name {}!'.format(repo_name), err=True)
                sys.exit(1)
            repo_suites = [repo_suite]
        else:
            repo_suites = session.query(ArchiveRepoSuiteSettings).all()

        for rss in repo_suites:
            if rss.frozen:
                continue
            expire_superseded(session, rss)


@click.command('copy-package')
@click.option(
    '--repo',
    'repo_name',
    default=None,
    help='Name of the repository to act on, if not set the default repository will be used.',
)
@click.option(
    '--version',
    'pkg_version',
    default=None,
    help='Copy an explicit version of a package.',
)
@click.argument('suite_from', nargs=1, required=True)
@click.argument('suite_to', nargs=1, required=True)
@click.argument('pkgname', nargs=1, required=True)
def cmd_copy_package(
    suite_from: str,
    suite_to: str,
    pkgname: str,
    *,
    pkg_version: T.Optional[str] = None,
    repo_name: T.Optional[str] = None,
):
    """Copy a source package from one suite to another."""

    if not repo_name:
        lconf = LocalConfig()
        repo_name = lconf.master_repo_name

    with session_scope() as session:
        rss_dest = repo_suite_settings_for(session, repo_name, suite_to, fail_if_missing=False)
        if not rss_dest:
            click.echo('Suite / repository configuration not found for {} in {}.'.format(suite_to, repo_name), err=True)
            sys.exit(4)
        rss_src = repo_suite_settings_for(session, repo_name, suite_from, fail_if_missing=False)
        if not rss_dest:
            click.echo('Suite / repository configuration not found for {} in {}.'.format(suite_to, repo_name), err=True)
            sys.exit(4)

        if pkg_version:
            spkg = (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.name == pkgname,
                    SourcePackage.repo_id == rss_src.repo_id,
                    SourcePackage.suites.any(id=rss_src.suite_id),
                    SourcePackage.version == pkg_version,
                    SourcePackage.time_deleted.is_(None),
                )
                .one_or_none()
            )
            if not spkg:
                click.echo('Package {} {} was not found in {}.'.format(pkgname, pkg_version, suite_from), err=True)
                sys.exit(4)
        else:
            spkg = find_latest_source_package(session, rss_src, pkgname)
            if not spkg:
                click.echo('Package {} was not found in {}.'.format(pkgname, suite_from), err=True)
                sys.exit(4)

        # now copy the package between suites
        copy_source_package(session, spkg, rss_dest)
