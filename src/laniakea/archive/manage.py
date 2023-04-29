# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import functools
from datetime import datetime, timedelta
from collections import namedtuple
from dataclasses import field, dataclass

from sqlalchemy import and_, func
from sqlalchemy.orm import joinedload

import laniakea.typing as T
from laniakea.db import (
    ArchiveError,
    ArchiveSuite,
    BinaryPackage,
    SourcePackage,
    PackageOverride,
    ArchiveRepository,
    SoftwareComponent,
    ArchiveArchitecture,
    ArchiveRepoSuiteSettings,
    package_version_compare,
)
from laniakea.logging import log, archive_log
from laniakea.archive.utils import package_mark_published


class ArchiveRemoveError(ArchiveError):
    """Failed to remove an entity from the package archive."""


def remove_binary_package(session, rss, bpkg: BinaryPackage) -> bool:
    """Remove a binary package from the archive.
    This function will unconditionally delete a specific binary package from the archive.
    If the source package it belongs to is still in many suites, this will lead to issues like
    package installability problems and needless rebuilds.
    You usually only want to call this function if the source package was removed with the binary.

    :param session: SQLAlchemy session.
    :param rss: The repo/suite to remove the package from
    :param bpkg: The binary package to remove
    :return: True if the package was removed, False if not found
    """

    # sanity check
    if bpkg.repo_id != rss.repo_id:
        raise ArchiveRemoveError(
            'Can not remove `{}/{}` from repository `{}` as it is not a member of it (belongs to `{}` instead).'.format(
                bpkg.name, bpkg.version, rss.repo.name, bpkg.repo.name
            )
        )
    if rss.frozen:
        raise ArchiveRemoveError(
            'Will not remove `{}/{}` from frozen `{}/{}`.'.format(
                bpkg.name, bpkg.version, rss.repo.name, rss.suite.name
            )
        )

    log.info('Deleting orphaned binary package %s', str(bpkg))
    bin_fname_full = os.path.join(rss.repo.get_root_dir(), bpkg.bin_file.fname)
    os.remove(bin_fname_full)
    session.delete(bpkg.bin_file)
    session.delete(bpkg)
    archive_log.info('DELETED-ORPHAN-BIN: %s/%s @ %s/%s', bpkg.name, bpkg.version, rss.repo.name, rss.suite.name)
    return True


def remove_source_package(session, rss: ArchiveRepoSuiteSettings, spkg: SourcePackage) -> bool:
    """Delete package from the archive
    This will completely remove the selected source package from a repository/suite configuration.
    :param session: SQLAlchemy session
    :param rss: The repo/suite to remove the package from
    :param spkg: The package to remove
    :return: True if the package was removed, False if not found
    """

    # sanity check
    if spkg.repo_id != rss.repo_id:
        raise ArchiveRemoveError(
            'Can not remove `{}/{}` from repository `{}` as it is not a member of it (belongs to `{}` instead).'.format(
                spkg.name, spkg.version, rss.repo.name, spkg.repo.name
            )
        )
    if rss.frozen:
        raise ArchiveRemoveError(
            'Will not remove source `{}/{}` from frozen `{}/{}`.'.format(
                spkg.name, spkg.version, rss.repo.name, rss.suite.name
            )
        )

    if spkg.suites:
        log.info('Removing package %s from suite %s', str(spkg), rss.suite.name)
        spkg.suites.remove(rss.suite)
        if spkg.suites:
            archive_log.info('DELETED-SRC-SUITE: %s/%s @ %s/%s', spkg.name, spkg.version, rss.repo.name, rss.suite.name)
    if not spkg.suites:
        log.info('Deleting orphaned package %s', str(spkg))
        # the package no longer is in any suites, remove it completely
        repo_root_dir = rss.repo.get_root_dir()
        srcpkg_repo_dir = os.path.join(repo_root_dir, spkg.directory)
        for bpkg in spkg.binaries:
            # remove binary packages completely (we just need any suite it is in to construct the RSS)
            bpkg_suite = bpkg.suites[0] if bpkg.suites else rss.suite
            bpkg_rss = (
                session.query(ArchiveRepoSuiteSettings)
                .filter(
                    ArchiveRepoSuiteSettings.repo.has(id=bpkg.repo_id),
                    ArchiveRepoSuiteSettings.suite.has(id=bpkg_suite.id),
                )
                .one_or_none()
            )
            if not bpkg_rss:
                raise ArchiveRemoveError(
                    'Unable to find suite configuration "{}/{}" for "{}"'.format(
                        bpkg_rss.repo.name, bpkg_rss.suite.name, str(bpkg)
                    )
                )
            # drop the associated binary, even if it might be in a different repository
            remove_binary_package(session, bpkg_rss, bpkg)

            # the source package is *completely* gone from this repository, so there is no need
            # to keep overrides around - we just drop them if no other source has adopted them.
            source_ids = (
                session.query(BinaryPackage.source_id)
                .filter(BinaryPackage.repo_id == rss.repo_id, BinaryPackage.name == bpkg.name)
                .all()
            )
            binary_adopted = False
            if source_ids:
                for sid_tp in source_ids:
                    if sid_tp[0] != bpkg.source_id:
                        binary_adopted = True
                        break

            if not binary_adopted:
                overrides = (
                    session.query(PackageOverride)
                    .filter(PackageOverride.repo_id == rss.repo_id, PackageOverride.pkg_name == bpkg.name)
                    .all()
                )
                for override in overrides:
                    session.delete(override)

        for file in spkg.files:
            # check if any other source package (likely one with a different revision) also holds a reference
            # on the same source file, and only delete the file from disk if it is an orphan
            other_owner = (
                session.query(SourcePackage.uuid)
                .filter(SourcePackage.files.any(id=file.id), SourcePackage.uuid != spkg.uuid)
                .first()
            )
            if not other_owner:
                fname_full = os.path.join(repo_root_dir, file.fname)
                os.unlink(fname_full)
                session.delete(file)
        if not os.listdir(srcpkg_repo_dir):
            os.rmdir(srcpkg_repo_dir)
        session.delete(spkg)
        archive_log.info('DELETED-SRC: %s/%s @ %s', spkg.name, spkg.version, rss.repo.name)

    return True


def package_mark_delete(session, rss: ArchiveRepoSuiteSettings, pkg: T.Union[BinaryPackage, SourcePackage]):
    """Mark a package for removal from the selected suite.
    The package will be removed from the selected repo/suite immediately, and if it is dropped from
    the repository entirely it will be marked for garbage collection rather than being deleted instantly.

    :param session: SQLAlchemy session
    :param rss: The repo/suite to delete the package from.
    :param pkg: The source or binary package to remove.
    :return:
    """

    # sanity check
    if pkg.repo_id != rss.repo_id:
        raise ArchiveRemoveError(
            'Can not mark `{}/{}` for removal from repository `{}` as it is not a member of it (belongs to `{}` instead).'.format(
                pkg.name, pkg.version, rss.repo.name, pkg.repo.name
            )
        )
    if rss.frozen:
        raise ArchiveRemoveError(
            'Will not mark package `{}/{}` for removal from frozen `{}/{}`.'.format(
                pkg.name, pkg.version, rss.repo.name, rss.suite.name
            )
        )

    is_src_pkg = type(pkg) is SourcePackage

    log.info('Removing package %s from suite %s', str(pkg), rss.suite.name)
    pkg.suites.remove(rss.suite)

    if pkg.suites:
        archive_log.info(
            '%s: %s/%s @ %s/%s',
            'DELETED-SUITE-SRC' if is_src_pkg else 'DELETED-SUITE-BIN',
            pkg.name,
            pkg.version,
            rss.repo.name,
            rss.suite.name,
        )
    else:
        log.info('Marking package for removal: %s', str(pkg))
        pkg.time_deleted = datetime.utcnow()
        archive_log.info(
            '%s: %s/%s @ %s/%s',
            'MARKED-REMOVAL-SRC' if is_src_pkg else 'MARKED-REMOVAL-BIN',
            pkg.name,
            pkg.version,
            rss.repo.name,
            rss.suite.name,
        )
    if is_src_pkg:
        for bpkg in pkg.binaries:
            if rss.suite in bpkg.suites:
                bpkg.suites.remove(rss.suite)
            if bpkg.suites:
                archive_log.info(
                    'DELETED-SUITE-BIN: %s/%s @ %s/%s', bpkg.name, bpkg.version, rss.repo.name, rss.suite.name
                )
            else:
                log.info('Marking binary for removal: %s', str(bpkg))
                bpkg.time_deleted = datetime.utcnow()
                archive_log.info('MARKED-REMOVAL-BIN: %s/%s @ %s', bpkg.name, bpkg.version, rss.repo.name)


def expire_superseded(session, rss: ArchiveRepoSuiteSettings, *, retention_days=14) -> None:
    """Remove superseded packages from the archive.
    This function will remove cruft packages in the selected repo/suite that have a higher version
    available and are no longer needed to be kept around.

    :param session: SQLAlchemy session
    :param rss: The repository/suite combo to act on
    """

    if rss.frozen:
        raise ArchiveError('Will not expire old packages in frozen suite `{}/{}`'.format(rss.repo.name, rss.suite.name))

    log.info("Checking %s:%s: Gathering information", rss.repo.name, rss.suite.name)

    @dataclass
    class PackageExpireInfo:
        name: str
        max_version: str
        max_version_has_binaries: bool = True
        rm_candidates: list[SourcePackage] = field(default_factory=list)

    spkg_filters = [
        SourcePackage.repo_id == rss.repo_id,
        SourcePackage.suites.any(id=rss.suite_id),
        SourcePackage.time_deleted.is_(None),
    ]

    spkg_filter_sq = session.query(SourcePackage).filter(*spkg_filters).subquery()
    smv_sq = (
        session.query(spkg_filter_sq.c.name, func.max(spkg_filter_sq.c.version).label('max_version'))
        .group_by(spkg_filter_sq.c.name)
        .subquery('smv_sq')
    )

    # get the latest source packages for this configuration
    log.debug("Retrieving maximum source package version information.")
    spkg_einfo = (
        session.query(SourcePackage.name, SourcePackage.version)
        .filter(*spkg_filters)
        .join(
            smv_sq,
            and_(
                SourcePackage.name == smv_sq.c.name,
                SourcePackage.version == smv_sq.c.max_version,
            ),
        )
        .all()
    )

    log.debug("Collecting list of all source packages.")
    all_spkgs = (
        session.query(SourcePackage)
        .options(joinedload(SourcePackage.binaries))
        .filter(
            SourcePackage.repo_id == rss.repo_id,
            SourcePackage.suites.any(id=rss.suite_id),
            SourcePackage.time_deleted.is_(None),
        )
        .all()
    )

    log.debug("Determining packages to remove.")
    # create a map of the latest source package versions
    pkg_expire_map = {}
    for info in spkg_einfo:
        ei = PackageExpireInfo(name=info[0], max_version=info[1])
        pkg_expire_map[ei.name] = ei
    del spkg_einfo

    # collect candidates for removal
    for spkg in all_spkgs:
        ei = pkg_expire_map[spkg.name]

        # we always want to keep the latest version of a package
        if spkg.version == ei.max_version:
            ei.max_version_has_binaries = True if spkg.binaries else False
            continue
        ei.rm_candidates.append(spkg)

    # check removal candidates and drop superseded ones
    log.info("Marking expired packages as superseded")
    for ei in pkg_expire_map.values():
        rm_candidates = ei.rm_candidates
        if not ei.max_version_has_binaries:
            # the highest version does not have binaries (yet), so we can only remove
            # truly superseded packages
            if len(rm_candidates) == 1:
                continue
            candidates_sorted = sorted(rm_candidates, key=functools.cmp_to_key(package_version_compare), reverse=True)
            rm_candidates = []
            have_bins = False
            for candidate in candidates_sorted:
                if candidate.binaries:
                    # highest version with binaries was found, everything
                    # that follows it can be marked for deletion
                    have_bins = True
                    continue
                if have_bins:
                    rm_candidates.append(candidate)

        # mark all remaining candidates for removal
        for old_spkg in rm_candidates:
            old_spkg.suites.remove(rss.suite)
            if old_spkg.suites:
                log.info('Removed superseded package from suite %s: %s', rss.suite.name, str(old_spkg))
                archive_log.info('EXPIRE-SUITE-REMOVED: %s from %s', rss.suite.name, str(old_spkg))
            else:
                log.info('Marking superseded package for removal: %s', str(old_spkg))
                old_spkg.time_deleted = datetime.utcnow()
                archive_log.info('EXPIRE-MARK-DELETE: %s', str(old_spkg))

        # FIXME: The code above will remove a package as soon as it has a binary built on *any* architecture.
        # This is often not what we want, so we would need to check that the latest package has built on all
        # architectures where it has been built before. If we do that though, packages that drop architectures,
        # or make an arch:any package an arch:all package will get stuck here and not be removed.
        # Therefore, we are currently a bit aggressive with removals and catch any fallout using Britney and
        # the Debcheck infrastructure to fix issues quickly. Still, some smarter code would be useful here.

    # grab all the packages that we should physically delete as they have been marked for deletion for a while
    log.info("Deleting expired packages")
    time_cutoff = datetime.utcnow() - timedelta(days=retention_days)
    spkgs_delete = (
        session.query(SourcePackage)
        .filter(
            SourcePackage.repo_id == rss.repo_id,
            ~SourcePackage.time_deleted.is_(None),
            SourcePackage.time_deleted <= time_cutoff,
            # delete anything expired in the selected suite, or any expired entity that is
            # in the selected repo and has no suite associated with it anymore.
            SourcePackage.suites.any(id=rss.suite_id) | ~SourcePackage.suites.any(),
        )
        .all()
    )

    for spkg_rm in spkgs_delete:
        log.info('Removing package marked for removal for %s days: %s', retention_days, str(spkg_rm))
        remove_source_package(session, rss, spkg_rm)

    # delete orphaned AppStream metadata
    log.info("Removing expired AppStream component metadata")
    for cpt in session.query(SoftwareComponent).filter(~SoftwareComponent.pkgs_binary.any()).all():
        session.delete(cpt)
        archive_log.info('DELETED-SWCPT-ORPHAN: %s @ %s/%s', cpt.gcid, rss.repo.name, rss.suite.name)
    archive_log.info('EXPIRE-RUN-COMPLETED')


def copy_source_package(
    session,
    spkg: SourcePackage,
    dest_rss: ArchiveRepoSuiteSettings,
    *,
    include_binaries: bool = True,
    allow_missing_debug: bool = False,
    overrides_from_suite: T.Optional[str] = None,
):
    """Copies a source package (and linked binaries) into a destination suite.
    It is only allowed to move a package within a repository this way - moving a package between
    repositories is not supported and requires a new upload.

    :param session: SQLAlchemy session
    :param spkg: Source package to copy
    :param dest_rss: Destination repository/suite
    :param include_binaries: True if binaries built by this source package should be copied with it.
    :param allow_missing_debug: True if it is okay if the destination has no corresponding debug suite.
    :param overrides_from_suite: Set a suite name from which binary overrides should be obtained (None to pick any suite)
    :raise:
    """

    if spkg.repo_id != dest_rss.repo_id:
        raise ArchiveError('Directly copying a package between repositories is not allowed.')

    dest_suite = dest_rss.suite
    if dest_suite not in spkg.suites:
        spkg.suites.append(dest_suite)
        package_mark_published(session, dest_rss, spkg)
        log.info('Copied source package %s:%s/%s into %s', spkg.repo.name, spkg.name, spkg.version, dest_suite.name)
        archive_log.info(
            'COPY-SRC: %s/%s in %s to suite %s (%s)',
            spkg.name,
            spkg.version,
            spkg.repo.name,
            dest_suite.name,
            'with-binaries' if include_binaries else 'no-binaries',
        )
    if include_binaries:
        for bpkg in spkg.binaries:
            # ignore debug packages if the destination has no debug suite and allow_missing_debug is set
            if bpkg.repo.is_debug and not dest_suite.debug_suite and allow_missing_debug:
                continue
            copy_binary_package(session, bpkg, dest_rss)


def copy_binary_package_override(
    session, bpkg: BinaryPackage, repo: ArchiveRepository, dest_suite: ArchiveSuite, from_suite: T.Optional[str]
):
    """Copy override information for a specific binary package from one suite to another.

    :param session: A SQLAlchemy session
    :param bpkg: Binary package the override information belongs to.
    :param repo: Repository to act on.
    :param dest_suite: The destination suite to copy to.
    :param from_suite: The suite to copy information from, if applicable.
    :return:
    """
    origin_suite_name = from_suite if from_suite else bpkg.suites[0].name

    target_override = (
        session.query(PackageOverride)
        .filter(
            PackageOverride.repo_id == repo.id,
            PackageOverride.suite_id == dest_suite.id,
            PackageOverride.pkg_name == bpkg.name,
        )
        .one_or_none()
    )
    origin_override = (
        session.query(PackageOverride)
        .filter(
            PackageOverride.repo_id == repo.id,
            PackageOverride.suite.has(name=origin_suite_name),
            PackageOverride.pkg_name == bpkg.name,
        )
        .one_or_none()
    )
    if not origin_override:
        raise ArchiveError(
            'Can not copy binary package: No override information found in source suite {} for `{}`.'.format(
                origin_suite_name, bpkg
            )
        )
    if not target_override:
        target_override = PackageOverride(bpkg.name)
        session.add(target_override)

    target_override.repo = repo
    target_override.suite = dest_suite
    target_override.essential = origin_override.essential
    target_override.priority = origin_override.priority
    target_override.component = origin_override.component
    target_override.section = origin_override.section


def copy_binary_package(
    session, bpkg: BinaryPackage, dest_rss: ArchiveRepoSuiteSettings, *, overrides_from_suite: T.Optional[str] = None
):
    """Copies a binary package into a destination suite.
    It is only allowed to move a package within a repository this way - moving a package between
    repositories is not supported and requires a new upload.

    :param session: SQLAlchemy session
    :param bpkg: Binary package to copy
    :param dest_rss: Destination repository/suite
    :param overrides_from_suite: Set a suite name from which overrides should be copied (None to pick any suite)
    :raise:
    """

    dest_suite = dest_rss.suite
    dest_debug_suite = dest_suite.debug_suite
    if bpkg.component not in dest_suite.components:
        raise ArchiveError(
            'Can not copy package: Source component "{}" not in target suite "{}".'.format(
                bpkg.component.name, dest_suite.name
            )
        )
    if bpkg.repo.is_debug:
        # this package is in a debug repo and therefore a debug symbol package
        # we need to move it to the debug suite that corresponds to the target suite
        if not dest_debug_suite:
            # TODO: We should roll back the already made changes here, just in case this exception is caught and
            # the session is committed.
            raise ArchiveError(
                'Can not copy binary debug package: No corresponding debug suite found for `{}`.'.format(
                    dest_suite.name
                )
            )
        if dest_debug_suite not in bpkg.suites:
            copy_binary_package_override(session, bpkg, dest_rss.repo, dest_debug_suite, overrides_from_suite)
            bpkg.suites.append(dest_debug_suite)
            log.info(
                'Copied dbgsym package %s:%s/%s into %s', bpkg.repo.name, bpkg.name, bpkg.version, dest_debug_suite.name
            )
            archive_log.info(
                'COPY-BIN-DBG: %s/%s in %s to suite %s', bpkg.name, bpkg.version, bpkg.repo.name, dest_debug_suite.name
            )
    elif dest_suite not in bpkg.suites:
        copy_binary_package_override(session, bpkg, dest_rss.repo, dest_suite, overrides_from_suite)
        bpkg.suites.append(dest_suite)
        package_mark_published(session, dest_rss, bpkg)
        log.info('Copied binary package %s:%s/%s into %s', bpkg.repo.name, bpkg.name, bpkg.version, dest_suite.name)
        archive_log.info('COPY-BIN: %s/%s in %s to suite %s', bpkg.name, bpkg.version, bpkg.repo.name, dest_suite.name)


def retrieve_suite_package_maxver_baseinfo(session, rss: ArchiveRepoSuiteSettings):
    """
    Retrieve basic information about the most recent versions of source and binary packages in a suite.

    This function returns a list of source package entries, consisting of the package name as first,
    and package version as second entry, as well as a list of binary package entries, with the
    package name as first, version as second, and architecture as third entry.
    For all packages, only the most recent version will be returned.

    :param session: A SQLAlchemy session
    :param rss: The repository/suite combination to retrieve data for.
    :return: A tuple of a list of source package infos, and binary package infos.
    """

    PackageInfoTuple = namedtuple('PackageInfoTuple', 'source binary')

    spkg_filters = [
        SourcePackage.repo_id == rss.repo_id,
        SourcePackage.suites.any(id=rss.suite_id),
        SourcePackage.time_deleted.is_(None),
    ]

    spkg_filter_sq = session.query(SourcePackage).filter(*spkg_filters).subquery()
    smv_sq = (
        session.query(spkg_filter_sq.c.name, func.max(spkg_filter_sq.c.version).label('max_version'))
        .group_by(spkg_filter_sq.c.name)
        .subquery('smv_sq')
    )

    # get the latest source packages for this configuration
    spkg_einfo = (
        session.query(SourcePackage.name, SourcePackage.version)
        .filter(*spkg_filters)
        .join(
            smv_sq,
            and_(
                SourcePackage.name == smv_sq.c.name,
                SourcePackage.version == smv_sq.c.max_version,
            ),
        )
        .all()
    )

    bpkg_filters = [
        BinaryPackage.repo_id == rss.repo_id,
        BinaryPackage.suites.any(id=rss.suite_id),
        BinaryPackage.time_deleted.is_(None),
    ]

    bpkg_filter_sq = session.query(BinaryPackage).filter(*bpkg_filters).subquery()
    bmv_sq = (
        session.query(bpkg_filter_sq.c.name, func.max(bpkg_filter_sq.c.version).label('max_version'))
        .group_by(bpkg_filter_sq.c.name)
        .subquery('bmv_sq')
    )

    # get binary package info for target suite
    bpkg_einfo = (
        session.query(BinaryPackage.name, BinaryPackage.version, ArchiveArchitecture.name)
        .filter(*bpkg_filters)
        .join(BinaryPackage.architecture)
        .join(
            bmv_sq,
            and_(
                BinaryPackage.name == bmv_sq.c.name,
                BinaryPackage.version == bmv_sq.c.max_version,
            ),
        )
        .all()
    )

    return PackageInfoTuple(spkg_einfo, bpkg_einfo)
