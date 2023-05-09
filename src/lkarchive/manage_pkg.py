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
    ArchiveSection,
    PackageOverride,
    PackagePriority,
    ArchiveRepoSuiteSettings,
    session_scope,
)
from laniakea.utils import process_file_lock
from laniakea.archive import (
    remove_source_package,
    repo_suite_settings_for,
    find_latest_source_package,
)
from laniakea.archive.manage import (
    expire_superseded,
    copy_source_package,
    remove_binary_package,
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
def cmd_list(term: str, repo_name: T.Optional[str], suite_name: T.Optional[str]):
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

        # combine binary package data for display
        bpkg_by_arch: T.Dict[str, T.Any] = {}
        for bpkg in bpkgs:
            bpkid = '{}:{}/{}-{}'.format(bpkg.repo.name, bpkg.component.name, bpkg.name, bpkg.version)
            arch_str = '[red]{}[/red]'.format(bpkg.architecture.name) if bpkg.time_deleted else bpkg.architecture.name
            if bpkid in bpkg_by_arch:
                bpkg_by_arch[bpkid]['archs'].add(arch_str)
                bpkg_by_arch[bpkid]['suites'].update([s.name for s in bpkg.suites])
            else:
                bpkg_by_arch[bpkid] = dict(bpkg=bpkg, archs={arch_str}, suites=set([s.name for s in bpkg.suites]))

        # sort the result list by source-version
        all_pkg_info = []
        for data in bpkg_by_arch.values():
            bpkg = data['bpkg']
            all_pkg_info.append(('{}-{}'.format(bpkg.source.name, bpkg.source.version), data))
        for spkg in spkgs:
            all_pkg_info.append(('{}-{}'.format(spkg.name, spkg.version), spkg))
        all_pkg_info.sort(key=lambda x: x[0])

        # display the result
        for _, info in all_pkg_info:
            if isinstance(info, SourcePackage):
                spkg = info
                table.add_row(
                    '[red]' + spkg.name if spkg.time_deleted else spkg.name,
                    spkg.version,
                    spkg.repo.name,
                    ' '.join(sorted([s.name for s in spkg.suites])),
                    spkg.component.name,
                    '[red]source (deleted)' if spkg.time_deleted else 'source',
                )
            else:
                bpkg = info['bpkg']
                table.add_row(
                    bpkg.name,
                    bpkg.version,
                    bpkg.repo.name,
                    ' '.join(sorted(info['suites'])),
                    bpkg.component.name,
                    ' '.join(sorted(info['archs'])),
                )

        console = Console()
        console.print(table)


def print_package_details(pkgs: list[SourcePackage] | list[BinaryPackage]):
    is_source = isinstance(pkgs[0], SourcePackage)

    table = Table(box=rich.box.MINIMAL)
    table.add_column('Package', no_wrap=True)
    table.add_column('Version', style='magenta', no_wrap=True)
    table.add_column('Repository')
    table.add_column('Suites')
    table.add_column('Component')
    if is_source:
        table.add_column('Binaries')
    else:
        table.add_column('Architecture')

    for pkg in pkgs:
        table.add_row(
            pkg.name if is_source else '{} ({})'.format(pkg.name, pkg.source.name),
            pkg.version,
            pkg.repo.name,
            ' '.join([s.name for s in pkg.suites]),
            pkg.component.name,
            ' '.join([b.name for b in pkg.binaries]) if is_source else pkg.architecture.name,
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
@click.option('--binary', 'is_binary', is_flag=True, default=False, help='The targeted package is a binary package')
@click.argument('pkgname', nargs=1)
def remove(pkgname: str, repo_name: T.Optional[str], suite_name: str, is_binary: bool = False):
    """Delete a source package (and its binaries) or a binary package."""

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

        if not is_binary:
            # we want to delete a source package
            spkgs = (
                session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.suites.any(id=rss.suite_id),
                    SourcePackage.name == pkgname,
                )
                .all()
            )

            if not spkgs:
                click.echo('Package {} not found in repository {}/{}.'.format(pkgname, repo_name, suite_name))
                sys.exit(0)

            print_package_details(spkgs)
            remove_confirmed = Confirm.ask('Do you really want to delete these packages?', default=False)

            if remove_confirmed:
                for spkg in spkgs:
                    remove_source_package(session, rss, spkg)
        else:
            # we want to remove a binary package
            bpkgs = (
                session.query(BinaryPackage)
                .filter(
                    BinaryPackage.repo_id == rss.repo_id,
                    BinaryPackage.suites.any(id=rss.suite_id),
                    BinaryPackage.name == pkgname,
                )
                .all()
            )

            if not bpkgs:
                click.echo('Binary package {} not found in repository {}/{}.'.format(pkgname, repo_name, suite_name))
                sys.exit(0)

            print_package_details(bpkgs)
            remove_confirmed = Confirm.ask('Do you really want to delete these binary packages?', default=False)

            if remove_confirmed:
                for bpkg in bpkgs:
                    remove_binary_package(session, rss, bpkg)


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
            with process_file_lock('archive_expire-{}'.format(rss.repo.name), wait=True):
                if rss.frozen:
                    continue
                with process_file_lock('publish_{}-{}'.format(rss.repo.name, rss.suite.name), wait=True):
                    expire_superseded(session, rss)
                    session.commit()


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


@click.command('show-overrides')
@click.option(
    '--repo',
    'repo_name',
    default=None,
    help='Name of the repository to act on, if not set all repositories will be checked',
)
@click.argument('pkgname', nargs=1)
def show_overrides(pkgname: str, repo_name: T.Optional[str]):
    """Show override information."""

    with session_scope() as session:
        # find source packages
        override_q = session.query(PackageOverride).filter(PackageOverride.pkg_name == pkgname)
        if repo_name:
            override_q = override_q.filter(PackageOverride.repo.has(name=repo_name))

        overrides = override_q.all()
        if not overrides:
            click.echo('Nothing found.', err=True)
            sys.exit(2)

        table = Table(box=rich.box.MINIMAL, title='Overrides for {}'.format(pkgname))
        table.add_column('Repo/Suite', no_wrap=True)
        table.add_column('Essential')
        table.add_column('Priority')
        table.add_column('Component')
        table.add_column('Section')

        overrides_sort = []
        for ov in overrides:
            overrides_sort.append(('{}/{}'.format(ov.repo.name, ov.suite.name), ov))
        overrides_sort.sort(key=lambda x: x[0])

        for suite_repo, ov in overrides_sort:
            table.add_row(
                suite_repo,
                'yes' if ov.essential else 'no',
                str(ov.priority),
                ov.component.name,
                ov.section.name,
            )

        console = Console()
        console.print(table)


@click.command('change-override')
@click.option(
    '--repo',
    'repo_name',
    default=None,
    help='Name of the repository to act on, if not set the default repository will be used.',
)
@click.option('--suite', 'suite_name', prompt=True, type=str, help='Name of the suite to work on')
@click.option('--essential', 'is_essential', type=str, help='Whether the package is marked as essential.')
@click.argument('pkgname', nargs=1, required=True)
@click.argument('priority_name', nargs=1, required=True)
@click.argument('section_name', nargs=1, required=True)
def change_override(
    suite_name: str,
    is_essential: str,
    pkgname: str,
    priority_name: str,
    section_name: str,
    *,
    repo_name: T.Optional[str] = None,
):
    """Change an override to the given values."""

    if not repo_name:
        lconf = LocalConfig()
        repo_name = lconf.master_repo_name

    with session_scope() as session:
        ov = (
            session.query(PackageOverride)
            .filter(
                PackageOverride.repo.has(name=repo_name),
                PackageOverride.suite.has(name=suite_name),
                PackageOverride.pkg_name == pkgname,
            )
            .one_or_none()
        )
        if not ov:
            click.echo('Unable to find override for "{}" in {}/{}.'.format(pkgname, repo_name, suite_name), err=True)
            sys.exit(2)

        priority = PackagePriority.from_string(priority_name)
        if priority == PackagePriority.UNKNOWN:
            click.echo('Priority value "{}" is unknown!'.format(priority_name), err=True)
            sys.exit(2)

        section = session.query(ArchiveSection).filter(ArchiveSection.name == section_name).one_or_none()
        if not section:
            click.echo('Section "{}" is unknown!'.format(section_name), err=True)
            sys.exit(2)

        if is_essential == 'yes':
            ov.essential = True
        elif is_essential == 'no':
            ov.essential = False

        ov.priority = priority
        ov.section = section
