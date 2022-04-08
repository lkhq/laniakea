# -*- coding: utf-8 -*-
#
# Copyright (C) 2021-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import sys
import fnmatch

import click
from sqlalchemy import and_, func

import laniakea.typing as T
from laniakea import LocalConfig
from laniakea.db import (
    NewPolicy,
    BinaryPackage,
    SourcePackage,
    ArchiveRepository,
    ArchiveArchitecture,
    ArchiveRepoSuiteSettings,
    session_scope,
)
from laniakea.archive import repo_suite_settings_for
from laniakea.logging import log
from laniakea.archive.manage import (
    copy_binary_package,
    copy_source_package,
    package_mark_delete,
)
from laniakea.archive.pkgimport import PackageImporter, ArchivePackageExistsError


def import_packages(
    session, rss: ArchiveRepoSuiteSettings, component_name: T.Optional[str], fnames: T.List[T.PathUnion]
):
    """Directly add packages to a repository, without any extra checks.
    Usually, a regulr upload will have a NEW review and a bunch of QA checks before being permitted into
    a repository, but occasionally a direct package import is useful too, which is what this command permits.
    """

    src_fnames = []
    bin_fnames = []
    for fname in fnames:
        if fname.endswith('.dsc'):
            src_fnames.append(fname)
        elif fname.endswith(('.deb', '.udeb')):
            bin_fnames.append(fname)
        elif fnmatch.fnmatch(fname, '*.tar.*') or fname.endswith(('.gz', '.buildinfo', '.changes')):
            # ignore source package components
            pass
        else:
            raise ValueError('File "{}" is no valid source or binary package!'.format(fname))

    if not src_fnames and not bin_fnames:
        raise ValueError('No valid source or binary packages found to import!')

    pi = PackageImporter(session, rss)
    pi.keep_source_packages = True

    # import sources
    for src_fname in src_fnames:
        try:
            pi.import_source(src_fname, component_name, new_policy=NewPolicy.NEVER_NEW)
        except ArchivePackageExistsError:
            log.info('Skipping %s: Already exists in the archive', os.path.basename(src_fname))
    session.commit()

    # import binaries
    for bin_fname in bin_fnames:
        try:
            pi.import_binary(bin_fname, component_name)
        except ArchivePackageExistsError:
            log.info('Skipping %s: Already exists in the archive', os.path.basename(bin_fname))


@click.command('import')
@click.option(
    '--repo',
    'repo_name',
    default=None,
    help='Name of the repository to act on, if not set the default repository is used.',
)
@click.option(
    '--suite',
    '-s',
    'suite_name',
    help='Name of the suite to act on, if not set all suites will be processed',
)
@click.option(
    '--component',
    '-c',
    'component_name',
    help='Name of the component to import into, will be read from the package file if not set.',
)
@click.argument('fnames', nargs=-1, type=click.Path())
def import_pkg(
    repo_name: T.Optional[str], suite_name: str, component_name: T.Optional[str], fnames: T.List[T.PathUnion]
):
    """Directly import packages into a repository, without any extra checks."""

    if not repo_name:
        lconf = LocalConfig()
        repo_name = lconf.master_repo_name

    if not fnames:
        click.echo('Nothing to import.', err=True)
        sys.exit(1)

    with session_scope() as session:
        repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == repo_name).one_or_none()
        if not repo:
            click.echo('Unable to find repository with name {}!'.format(repo_name), err=True)
            sys.exit(1)

        rss = (
            session.query(ArchiveRepoSuiteSettings)
            .filter(ArchiveRepoSuiteSettings.repo_id == repo.id, ArchiveRepoSuiteSettings.suite.has(name=suite_name))
            .one_or_none()
        )
        if not rss:
            click.echo('Unable to find suite "{}" in repository "{}"'.format(suite_name, repo_name), err=True)
            sys.exit(1)

        try:
            import_packages(session, rss, component_name, fnames)
        except Exception as e:
            click.echo('Package import failed: {}'.format(str(e)), err=True)
            sys.exit(5)


@click.command('import-heidi')
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
    help='Name of the suite to act on.',
)
@click.option(
    '--with-rm',
    'allow_delete',
    default=False,
    is_flag=True,
    help='Set the suite contents to exactly the Britney result (allows removal of packages and overrides all suite contents).',
)
@click.argument('heidi_fname', nargs=1, type=click.Path(), required=True)
def import_heidi_result(
    suite_name: str, heidi_fname: T.List[T.PathUnion], repo_name: T.Optional[str] = None, allow_delete: bool = False
):
    """Import a HeidiResult file from Britney to migrate packages."""

    if not repo_name:
        lconf = LocalConfig()
        repo_name = lconf.master_repo_name

    with session_scope() as session:
        rss = repo_suite_settings_for(session, repo_name, suite_name, fail_if_missing=False)
        if not rss:
            click.echo(
                'Suite / repository configuration not found for {} in {}.'.format(suite_name, repo_name), err=True
            )
            sys.exit(4)

        smv_subq = (
            session.query(SourcePackage.name, func.max(SourcePackage.version).label('max_version'))
            .group_by(SourcePackage.name)
            .subquery('smv_subq')
        )

        # get the latest source packages for this configuration
        spkg_einfo = (
            session.query(SourcePackage.name, SourcePackage.version)
            .join(
                smv_subq,
                and_(
                    SourcePackage.name == smv_subq.c.name,
                    SourcePackage.repo_id == rss.repo_id,
                    SourcePackage.suites.any(id=rss.suite_id),
                    SourcePackage.version == smv_subq.c.max_version,
                    SourcePackage.time_deleted.is_(None),
                ),
            )
            .all()
        )
        spkg_eset = {}
        for info in spkg_einfo:
            spkg_eset[info[0]] = info[1]

        bmv_subq = (
            session.query(BinaryPackage.name, func.max(BinaryPackage.version).label('max_version'))
            .group_by(BinaryPackage.name)
            .subquery('bmv_subq')
        )

        # get binary package info for target suite
        bpkg_einfo = (
            session.query(BinaryPackage.name, BinaryPackage.version, ArchiveArchitecture.name)
            .join(BinaryPackage.architecture)
            .join(
                bmv_subq,
                and_(
                    BinaryPackage.name == bmv_subq.c.name,
                    BinaryPackage.repo_id == rss.repo_id,
                    BinaryPackage.suites.any(id=rss.suite_id),
                    BinaryPackage.version == bmv_subq.c.max_version,
                    BinaryPackage.time_deleted.is_(None),
                ),
            )
            .all()
        )
        bpkg_eset = {}
        for info in bpkg_einfo:
            bpkg_eset[info[0] + '-' + info[2]] = (info[0], info[1], info[2])

        arch_ref = {}
        for arch in rss.suite.architectures:
            arch_ref[arch.name] = arch

        with open(heidi_fname, 'r', encoding='utf-8') as f:
            while line := f.readline():
                pkgname, pkgversion, arch_name, section_full = line.rstrip().split(' ', 3)

                if arch_name == 'source':
                    # handle source package migration
                    e_version = spkg_eset.pop(pkgname, None)
                    if not e_version or pkgversion != e_version:
                        # package not present in target, or is present in a different version.
                        # Let's look for this version in the current repository and copy it to the target
                        spkg = (
                            session.query(SourcePackage)
                            .filter(
                                SourcePackage.repo_id == rss.repo_id,
                                SourcePackage.name == pkgname,
                                SourcePackage.version == pkgversion,
                            )
                            .one()
                        )
                        copy_source_package(session, spkg, rss, include_binaries=False)
                        continue
                else:
                    _, e_version, e_arch_name = bpkg_eset.pop(pkgname + arch_name, (None, None, None))
                    if not e_version or e_version != pkgversion:
                        arch = arch_ref[arch_name]
                        bpkg = (
                            session.query(BinaryPackage)
                            .filter(
                                BinaryPackage.repo_id == rss.repo_id,
                                BinaryPackage.name == pkgname,
                                BinaryPackage.version == pkgversion,
                                BinaryPackage.architecture.has(id=arch.id),
                            )
                            .one()
                        )
                        copy_binary_package(session, bpkg, rss)
                        # FIXME: We also need to move the debug package here, if one the corresponds to the binary package exists
                        continue

        if allow_delete:
            for pkgname_rm, version_rm in spkg_eset.items():
                spkg = (
                    session.query(SourcePackage)
                    .filter(
                        SourcePackage.repo_id == rss.repo_id,
                        SourcePackage.name == pkgname_rm,
                        SourcePackage.version == version_rm,
                    )
                    .one()
                )
                package_mark_delete(session, rss, spkg)

            for pkgname_rm, version_rm, arch_name_rm in bpkg_eset.values():
                arch_rm = arch_ref[arch_name_rm]
                bpkg = (
                    session.query(BinaryPackage)
                    .filter(
                        BinaryPackage.repo_id == rss.repo_id,
                        BinaryPackage.name == pkgname_rm,
                        BinaryPackage.version == version_rm,
                        BinaryPackage.architecture.has(id=arch_rm.id),
                    )
                    .one()
                )
                package_mark_delete(session, rss, bpkg)
