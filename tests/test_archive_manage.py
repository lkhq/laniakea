# -*- coding: utf-8 -*-
#
# Copyright (C) 2024-2026 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from datetime import UTC, datetime

from laniakea.db import (
    ArchiveSuite,
    BinaryPackage,
    ArchiveSection,
    PackageOverride,
    PackagePriority,
    ArchiveComponent,
    ArchiveRepository,
    ArchiveArchitecture,
    session_scope,
)
from laniakea.archive.utils import repo_suite_settings_for
from laniakea.archive.manage import copy_binary_package


def _add_override(
    session, repo: ArchiveRepository, suite: ArchiveSuite, pkgname: str, section_name: str, priority: PackagePriority
) -> PackageOverride:
    override = PackageOverride(pkgname, repo, suite)
    override.component = session.query(ArchiveComponent).filter(ArchiveComponent.name == 'main').one()
    override.section = session.query(ArchiveSection).filter(ArchiveSection.name == section_name).one()
    override.priority = priority
    session.add(override)

    return override


def _add_zombie_binary_package(session, repo: ArchiveRepository, name: str, version: str) -> BinaryPackage:
    """Register a binary package that is in no suite anymore and was marked for removal."""

    bpkg = BinaryPackage(name, version, repo)
    bpkg.component = session.query(ArchiveComponent).filter(ArchiveComponent.name == 'main').one()
    bpkg.architecture = session.query(ArchiveArchitecture).filter(ArchiveArchitecture.name == 'amd64').one()
    bpkg.update_uuid()
    bpkg.size_installed = 1
    bpkg.summary = 'Test package'
    bpkg.description = 'Test package'
    bpkg.description_md5 = '0' * 32
    bpkg.maintainer = 'A Maintainer <maint@example.com>'
    bpkg.time_deleted = datetime.now(UTC)
    session.add(bpkg)

    return bpkg


def _get_override(session, repo: ArchiveRepository, suite: ArchiveSuite, pkgname: str) -> PackageOverride:
    return (
        session.query(PackageOverride)
        .filter(
            PackageOverride.repo_id == repo.id,
            PackageOverride.suite_id == suite.id,
            PackageOverride.pkg_name == pkgname,
        )
        .one()
    )


def test_copy_zombie_override_from_other_suite(database):
    """
    A deleted binary package that is brought back into a suite it was never in before has to
    take its override from a different suite (#57).
    """

    with session_scope() as session:
        rss_unstable = repo_suite_settings_for(session, 'master', 'unstable')
        rss_stable = repo_suite_settings_for(session, 'master', 'stable')
        repo = rss_stable.repo

        # the package was in unstable once and got removed from it, but its override is still around
        bpkg = _add_zombie_binary_package(session, repo, 'linux-headers-1.0-common', '1.0-1')
        _add_override(session, repo, rss_unstable.suite, bpkg.name, 'kernel', PackagePriority.IMPORTANT)
        session.flush()

        copy_binary_package(session, bpkg, rss_stable)
        session.flush()

        assert bpkg.suites == [rss_stable.suite]
        assert bpkg.time_deleted is None

        override = _get_override(session, repo, rss_stable.suite, bpkg.name)
        assert override.section.name == 'kernel'
        assert override.priority == PackagePriority.IMPORTANT
        assert override.component.name == 'main'


def test_copy_zombie_override_prefers_target_suite(database):
    """If the target suite still has an override for a deleted package, it must not be replaced."""

    with session_scope() as session:
        rss_unstable = repo_suite_settings_for(session, 'master', 'unstable')
        rss_stable = repo_suite_settings_for(session, 'master', 'stable')
        repo = rss_stable.repo

        bpkg = _add_zombie_binary_package(session, repo, 'linux-source-1.0', '1.0-1')
        _add_override(session, repo, rss_unstable.suite, bpkg.name, 'kernel', PackagePriority.IMPORTANT)
        _add_override(session, repo, rss_stable.suite, bpkg.name, 'devel', PackagePriority.STANDARD)
        session.flush()

        copy_binary_package(session, bpkg, rss_stable)
        session.flush()

        assert bpkg.suites == [rss_stable.suite]
        assert bpkg.time_deleted is None

        override = _get_override(session, repo, rss_stable.suite, bpkg.name)
        assert override.section.name == 'devel'
        assert override.priority == PackagePriority.STANDARD
