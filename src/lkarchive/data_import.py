# -*- coding: utf-8 -*-
#
# Copyright (C) 2021-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import sys
import fnmatch

import click
from rich import print
from rich.panel import Panel
from rich.prompt import Confirm

import laniakea.typing as T
from laniakea import LocalConfig
from laniakea.db import (
    NewPolicy,
    PackageInfo,
    ArchiveSuite,
    BinaryPackage,
    SourcePackage,
    ArchiveSection,
    PackageOverride,
    ArchiveComponent,
    ArchiveRepository,
    ArchiveRepoSuiteSettings,
    session_scope,
)
from laniakea.archive import repo_suite_settings_for, repo_suite_settings_for_debug
from laniakea.logging import log
from laniakea.archive.manage import (
    copy_binary_package,
    copy_source_package,
    package_mark_delete,
    retrieve_suite_package_maxver_baseinfo,
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
        fname = str(fname)
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
@click.option('--suite', '-s', 'suite_name', help='Name of the suite to act on.', required=True)
@click.option(
    '--with-rm',
    'allow_delete',
    default=False,
    is_flag=True,
    help='Set the suite contents to exactly the Britney result (allows removal of packages and overrides all suite contents).',
)
@click.argument('heidi_fname', nargs=1, type=click.Path(), required=True)
def import_heidi_result(
    suite_name: str, heidi_fname: T.PathUnion, repo_name: T.Optional[str] = None, allow_delete: bool = False
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

        spkg_einfo, bpkg_einfo = retrieve_suite_package_maxver_baseinfo(session, rss)

        spkg_eset = {}
        for info in spkg_einfo:
            spkg_eset[info[0]] = info[1]

        bpkg_eset = {}
        for info in bpkg_einfo:
            bpkg_eset[info[0] + '/' + info[2]] = (info[0], info[1], info[2])

        arch_ref = {}
        for arch in rss.suite.architectures:
            arch_ref[arch.name] = arch

        with open(heidi_fname, 'r', encoding='utf-8') as f:
            while line := f.readline():
                line = line.rstrip()
                if not line:
                    # this may be the end of the file or the file might be completely empty
                    continue
                pkgname, pkgversion, arch_name = line.split(' ', 3)

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
                    _, e_version, e_arch_name = bpkg_eset.pop(pkgname + '/' + arch_name, (None, None, None))
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
                        # FIXME: We also need to move the debug package here, if one that corresponds to the binary package exists
                        continue

        if allow_delete:
            for pkgname_rm, version_rm in spkg_eset.items():
                spkg = (
                    session.query(SourcePackage)
                    .filter(
                        SourcePackage.repo_id == rss.repo_id,
                        SourcePackage.name == pkgname_rm,
                        SourcePackage.version == version_rm,
                        SourcePackage.suites.any(id=rss.suite_id),
                    )
                    .one_or_none()
                )
                if not spkg:
                    continue
                package_mark_delete(session, rss, spkg)

            for pkgname_rm, version_rm, arch_name_rm in bpkg_eset.values():
                arch_rm = arch_ref[arch_name_rm]
                bpkg = (
                    session.query(BinaryPackage)
                    .filter(
                        BinaryPackage.repo_id == rss.repo_id,
                        BinaryPackage.name == pkgname_rm,
                        BinaryPackage.version == version_rm,
                        BinaryPackage.suites.any(id=rss.suite_id),
                        BinaryPackage.architecture.has(id=arch_rm.id),
                    )
                    .one_or_none()
                )
                if not bpkg:
                    continue
                package_mark_delete(session, rss, bpkg)


@click.command('export-list')
@click.option(
    '--repo',
    'repo_name',
    default=None,
    help='Name of the repository to act on, if not set the default repository will be used.',
)
@click.option('--suite', '-s', 'suite_name', help='Name of the suite to act on.', required=True)
@click.argument('result_fname', nargs=1, type=click.Path(), required=True)
def export_package_list(suite_name: str, result_fname: T.PathUnion, repo_name: T.Optional[str] = None):
    """Export a list of all packages contained in the selected suite configuration."""

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

        spkg_einfo, bpkg_einfo = retrieve_suite_package_maxver_baseinfo(session, rss)
        with open(os.path.abspath(result_fname), 'w', encoding='utf-8') as f:
            for info in spkg_einfo:
                f.write('{} {} source\n'.format(info[0], info[1]))
            for info in bpkg_einfo:
                f.write('{} {} {}\n'.format(info[0], info[1], info[2]))


def _import_repo_into_suite(
    session,
    rss_dest: ArchiveRepoSuiteSettings,
    target_component_name: str,
    source_suite_name: str,
    source_component_name: str,
    src_repo_path: T.PathUnion,
):
    """Import a complete, local repository into a target."""
    from laniakea.reporeader import RepositoryReader
    from laniakea.archive.utils import register_package_overrides

    src_repo = RepositoryReader(src_repo_path, 'external')
    src_repo.set_trusted(True)
    src_suite = ArchiveSuite(source_suite_name)
    src_component = ArchiveComponent(source_component_name)

    rss_dest_dbg = repo_suite_settings_for_debug(session, rss_dest)
    if not rss_dest_dbg:
        rss_dest_dbg = rss_dest

    pi = PackageImporter(session, rss_dest)
    pi.keep_source_packages = True  # we must not delete the source while importing it
    pi.prefer_hardlinks = True  # prefer hardlinks if we are on the same drive, to safe space

    # import all source packages
    print(Panel.fit('Importing sources'))
    for spkg_src in src_repo.source_packages(src_suite, src_component):
        dscfile = None
        for f in spkg_src.files:
            # the source repository might be on a remote location, so we need to
            # request each file to be there.
            # (dak will fetch the files referenced in the .dsc file from the same directory)
            if f.fname.endswith('.dsc'):
                dscfile = src_repo.get_file(f)
            src_repo.get_file(f)

        if not dscfile:
            log.error(
                'Critical consistency error: Source package {}/{} in repository {} has no .dsc file.'.format(
                    spkg_src.name, spkg_src.version, src_repo.base_dir
                )
            )
            return False

        # we need to register overrides based on the source package info first, as
        # the dsc file may not contain sufficient data to auto-create them
        register_package_overrides(session, rss_dest, spkg_src.expected_binaries, allow_invalid_section=True)

        spkg_dst = (
            session.query(SourcePackage)
            .filter(
                SourcePackage.repo_id == rss_dest.repo_id,
                SourcePackage.name == spkg_src.name,
                SourcePackage.version == spkg_src.version,
            )
            .one_or_none()
        )

        # now actually import the source package, or register it with our suite if needed
        if spkg_dst:
            if rss_dest.suite not in spkg_dst.suites:
                spkg_dst.suites.append(rss_dest.suite)
            log.info('Processed source: %s/%s', spkg_dst.name, spkg_dst.version)
        else:
            pi.import_source(dscfile, target_component_name, new_policy=NewPolicy.NEVER_NEW, ignore_version_check=True)
    session.commit()

    # import all binary packages
    for arch in rss_dest.suite.architectures:
        print(Panel.fit('Importing binaries for {}'.format(arch.name)))
        shadow_arch = None
        if arch.name == 'all':
            for a in rss_dest.suite.architectures:
                if a.name != 'all':
                    shadow_arch = a
                    break
            log.info('Using shadow architecture %s for arch:all', shadow_arch.name)

        bin_pkgs = src_repo.binary_packages(src_suite, src_component, arch, shadow_arch=shadow_arch)
        bin_pkgs.extend(src_repo.installer_packages(src_suite, src_component, arch))
        for bpkg_src in bin_pkgs:
            fname = src_repo.get_file(bpkg_src.bin_file)

            rss_dest_real = rss_dest
            if bpkg_src.override.section == 'debug':
                # we have a debug package, which may live in a different repo/suite
                rss_dest_real = rss_dest_dbg

            bpkg_dst = (
                session.query(BinaryPackage)
                .filter(
                    BinaryPackage.repo_id == rss_dest_real.repo_id,
                    BinaryPackage.name == bpkg_src.name,
                    BinaryPackage.version == bpkg_src.version,
                    BinaryPackage.architecture.has(name=arch.name),
                )
                .one_or_none()
            )

            # update override to match the source data exactly
            # we check the non-debug primary repo-suite config (rss_dest) first
            override = (
                session.query(PackageOverride)
                .filter(PackageOverride.repo_suite_id == rss_dest.id, PackageOverride.pkgname == bpkg_src.name)
                .one_or_none()
            )
            if not override:
                # check the corresponding debug suite
                override = (
                    session.query(PackageOverride)
                    .filter(PackageOverride.repo_suite_id == rss_dest_dbg.id, PackageOverride.pkgname == bpkg_src.name)
                    .one_or_none()
                )
                if not override:
                    # If we are importing a repository with older packages (e.g. Debian's), we may not have set
                    # all the overrides correctly from source packages.
                    # So we cheat and add a new override based on the binary override data (will not work for debug
                    # packages, in which case we'll simply fail)
                    pinfo = PackageInfo(
                        deb_type=bpkg_src.deb_type,
                        name=bpkg_src.name,
                        version=bpkg_src.version,
                        component=src_component.name,
                        section=bpkg_src.override.section,
                        essential=bpkg_src.override.essential,
                        priority=bpkg_src.override.priority,
                        architectures=[arch.name],
                    )
                    register_package_overrides(session, rss_dest, [pinfo])
                    override = (
                        session.query(PackageOverride)
                        .filter(PackageOverride.repo_suite_id == rss_dest.id, PackageOverride.pkgname == bpkg_src.name)
                        .one_or_none()
                    )
                    if not override:
                        # check the corresponding debug suite
                        if rss_dest_dbg.id != rss_dest.id:
                            override = (
                                session.query(PackageOverride)
                                .filter(
                                    PackageOverride.repo_suite_id == rss_dest_dbg.id,
                                    PackageOverride.pkgname == bpkg_src.name,
                                )
                                .one_or_none()
                            )
                        if not override:
                            log.error(
                                (
                                    'Override missing unexpectedly: Binary package %s has no associated override in %s:%s, '
                                    'even though it was already imported.'
                                ),
                                bpkg_src.name,
                                rss_dest_real.repo.name,
                                rss_dest_real.suite.name,
                            )
                            if bpkg_src.override.section == 'debug':
                                continue
                            else:
                                return False
            override.repo_suite = rss_dest_real
            override.section = (
                session.query(ArchiveSection).filter(ArchiveSection.name == bpkg_src.override.section).one_or_none()
            )
            if not override.section:
                log.error(
                    'Archive section `%s` does not exist, even though `%s` thinks it does.',
                    bpkg_src.override.section,
                    bpkg_src.name,
                )
                return False
            override.essential = bpkg_src.override.essential
            override.priority = bpkg_src.override.priority

            # import binary package if needed
            if bpkg_dst:
                if rss_dest_real.suite not in bpkg_dst.suites:
                    bpkg_dst.suites.append(rss_dest_real.suite)
                log.info('Processed binary: %s/%s on %s', bpkg_dst.name, bpkg_dst.version, arch.name)
            else:
                pi.import_binary(fname, target_component_name, override_section=bpkg_src.override.section)

        # commit after each architecture was processed
        session.commit()


@click.command('import-repo')
@click.option(
    '--repo',
    'repo_name',
    default=None,
    help='Name of the repository to act on, if not set the default repository is used.',
)
@click.option(
    '--target-suite',
    'target_suite_name',
    required=True,
    help='Name of the suite to import into.',
)
@click.option(
    '--target-component',
    'target_component_name',
    required=True,
    help='Name of the component to import into.',
)
@click.option(
    '--source-suite',
    'source_suite',
    required=True,
    help='Name of the suite to import from.',
)
@click.option(
    '--source-component',
    'source_component',
    required=True,
    help='Name of the component to import from.',
)
@click.argument('src_repo_path', nargs=1, type=click.Path(), required=True)
def import_repository(
    repo_name: T.Optional[str],
    target_suite_name: str,
    target_component_name: str,
    source_suite: str,
    source_component: str,
    src_repo_path: T.PathUnion,
):
    """Import full contents of an external repository into a destination repository, copying it."""

    if not repo_name:
        lconf = LocalConfig()
        repo_name = lconf.master_repo_name

    with session_scope() as session:
        rss = repo_suite_settings_for(session, repo_name, target_suite_name, fail_if_missing=False)
        if not rss:
            click.echo(
                'Suite / repository configuration not found for {} in {}.'.format(target_suite_name, repo_name),
                err=True,
            )
            sys.exit(4)

        import_confirmed = Confirm.ask(
            'Do you really want to perform this import, overriding existing data in the destination?', default=False
        )
        if not import_confirmed:
            return
        if not _import_repo_into_suite(
            session, rss, target_component_name, source_suite, source_component, src_repo_path
        ):
            sys.exit(1)
