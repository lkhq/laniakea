# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os

import laniakea.typing as T
from laniakea.logging import log
from laniakea.db import BinaryPackage, SourcePackage, ArchiveRepoSuiteSettings


class ArchiveRemoveError(Exception):
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
