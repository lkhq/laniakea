# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
from datetime import datetime, timedelta

from sqlalchemy import and_, func

import laniakea.typing as T
from laniakea.db import (
    ArchiveError,
    ArchiveSuite,
    BinaryPackage,
    SourcePackage,
    ArchiveRepoSuiteSettings,
)
from laniakea.logging import log


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

    log.info('Removing package %s from suite %s', str(spkg), rss.suite.name)
    spkg.suites.remove(rss.suite)
    if not spkg.suites:
        log.info('Deleting orphaned package %s', str(spkg))
        # the package no longer is in any suites, remove it completely
        repo_root_dir = rss.repo.get_root_dir()
        srcpkg_repo_dir = os.path.join(repo_root_dir, spkg.directory)
        for bpkg in spkg.binaries:
            remove_binary_package(session, rss, bpkg)
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

    return True


def expire_superseded(session, rss: ArchiveRepoSuiteSettings) -> None:
    """Remove superseded packages from the archive.
    This function will remove cruft packages in the selected repo/suite that have a higher version
    available and are no longer needed to be kept around.

    :param session: SQLAlchemy session
    :param rss: The repository/suite combo to act on
    """

    if rss.frozen:
        raise ArchiveError('Will not expire old packages in frozen suite `{}/{}`'.format(rss.repo.name, rss.suite.name))

    smv_subq = (
        session.query(SourcePackage.name, func.max(SourcePackage.version).label('max_version'))
        .group_by(SourcePackage.name)
        .subquery('smv_subq')
    )

    # fetch the latest source package info
    # we will only include source packages which actually have binaries built.
    # TODO: this logic can be improved, e.g, we should make sure the package built on all arches
    latest_spkg_info = (
        session.query(SourcePackage.name, SourcePackage.version)
        .join(
            smv_subq,
            and_(
                SourcePackage.name == smv_subq.c.name,
                SourcePackage.repo_id == rss.repo_id,
                SourcePackage.suites.any(id=rss.suite_id),
                SourcePackage.version == smv_subq.c.max_version,
                SourcePackage.binaries.any(),
            ),
        )
        .all()
    )

    # TODO: A lot of this loop can likely be implemented as a more efficient SQL query
    for spkg_name, spkg_latest_ver in latest_spkg_info:
        # now drop any lower version that we find
        old_spkgs = (
            session.query(SourcePackage)
            .filter(
                SourcePackage.name == spkg_name,
                SourcePackage.repo_id == rss.repo_id,
                SourcePackage.suites.any(id=rss.suite_id),
                SourcePackage.version < spkg_latest_ver,
                SourcePackage.time_deleted.is_(None),
            )
            .all()
        )
        if not old_spkgs:
            continue
        for old_spkg in old_spkgs:
            log.info('Marking superseded package for removal: %s', str(old_spkg))
            old_spkg.time_deleted = datetime.utcnow()

    # grab all the packages that we should actively delete as they have been expired for a while
    retention_days = 14
    time_cutoff = datetime.utcnow() - timedelta(days=retention_days)
    spkgs_delete = (
        session.query(SourcePackage)
        .filter(
            SourcePackage.repo_id == rss.repo_id,
            SourcePackage.suites.any(id=rss.suite_id),
            SourcePackage.time_deleted != None,
            SourcePackage.time_deleted <= time_cutoff,
        )
        .all()
    )
    for spkg_rm in spkgs_delete:
        log.info('Removing package marked for removal for %s days: %s', retention_days, str(spkg_rm))
        remove_source_package(rss, spkg_rm)


def copy_package(session, spkg: SourcePackage, dest_rss: ArchiveRepoSuiteSettings):
    """Copies a package into a destination suite.
    It is only allowed to move a package within a repository this way - moving a package between
    repositories is not supported and requires a new upload.

    :param session: SQLAlchemy session
    :param spkg: Source package to copy
    :param dest_rss: Destination repository/suite
    :raise:
    """

    if spkg.repo_id != dest_rss.repo_id:
        raise ArchiveError('Can not directory copy a package between repositories.')

    dest_suite = dest_rss.suite
    dest_debug_suite = dest_rss.suite.debug_suite
    if dest_suite not in spkg.suites:
        spkg.suites.append(dest_suite)
    for bpkg in spkg.binaries:
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
                bpkg.suites.append(dest_debug_suite)
        elif dest_suite not in bpkg.suites:
            bpkg.suites.append(dest_suite)
