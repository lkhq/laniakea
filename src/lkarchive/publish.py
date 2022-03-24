# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import shutil
import typing as T
import hashlib
import subprocess

from apt_pkg import Hashes
from sqlalchemy import and_, func
from debian.deb822 import Deb822

from laniakea import LocalConfig
from laniakea.db import (
    ArchiveSuite,
    BinaryPackage,
    SourcePackage,
    ArchiveComponent,
    ArchiveRepository,
    ArchiveArchitecture,
    ArchiveRepoSuiteSettings,
    packagepriority_to_string,
)
from laniakea.logging import log


def set_deb822_value(entry: Deb822, key: str, value: str):
    if value:
        entry[key] = value


def generate_sources_index(session, repo: ArchiveRepository, suite: ArchiveSuite, component: ArchiveComponent):
    """
    Generate Sources index data for the given repo/suite/component.
    :param session: Active SQLAlchemy session
    :param repo: Repository to generate data for
    :param suite: Suite to generate data for
    :param component: Component to generate data for
    :return:
    """

    smv_subq = (
        session.query(SourcePackage.name, func.max(SourcePackage.version).label('max_version'))
        .group_by(SourcePackage.name)
        .subquery('t2')
    )

    # get the latest source packages for this configuration
    spkgs = (
        session.query(SourcePackage)
        .join(
            smv_subq,
            and_(
                SourcePackage.repo_id == repo.id,
                SourcePackage.suites.any(id=suite.id),
                SourcePackage.component_id == component.id,
                SourcePackage.version == smv_subq.c.max_version,
            ),
        )
        .order_by(SourcePackage.name)
        .all()
    )

    entries = []
    for spkg in spkgs:
        # write sources file
        entry = Deb822()
        set_deb822_value(entry, 'Package', spkg.name)
        set_deb822_value(entry, 'Version', spkg.version)
        set_deb822_value(entry, 'Binary', ', '.join([b.name for b in spkg.expected_binaries]))
        set_deb822_value(entry, 'Maintainer', spkg.maintainer)
        set_deb822_value(entry, 'Original-Maintainer', spkg.original_maintainer)
        set_deb822_value(entry, 'Uploaders', ', '.join(spkg.uploaders))

        set_deb822_value(entry, 'Architecture', ', '.join(spkg.architectures))
        set_deb822_value(entry, 'Format', spkg.format_version)
        set_deb822_value(entry, 'Standards-Version', spkg.standards_version)

        set_deb822_value(entry, 'Section', spkg.section)
        set_deb822_value(entry, 'Homepage', spkg.homepage)
        set_deb822_value(entry, 'Vcs-Browser', spkg.vcs_browser)

        set_deb822_value(entry, 'Build-Depends', ', '.join(spkg.build_depends))
        set_deb822_value(entry, 'Build-Depends-Indep', ', '.join(spkg.build_depends_indep))
        set_deb822_value(entry, 'Build-Conflicts', ', '.join(spkg.build_conflicts))
        set_deb822_value(entry, 'Build-Conflicts-Indep', ', '.join(spkg.build_conflicts_indep))

        set_deb822_value(entry, 'Directory', spkg.directory)
        cs_data = []
        for file in spkg.files:
            cs_data.append('{} {} {}'.format(file.sha256sum, file.size, file.fname))
        set_deb822_value(entry, 'Checksums-Sha256', '\n ' + '\n '.join(cs_data))

        for key, value in spkg.extra_data.items():
            set_deb822_value(entry, key, value)

        entries.append(entry.dump())

    return '\n'.join(entries)


def generate_packages_index(
    session, repo: ArchiveRepository, suite: ArchiveSuite, component: ArchiveComponent, arch: ArchiveArchitecture
):
    """
    Generate Packages index data for the given repo/suite/component/arch.
    :param session: Active SQLAlchemy session
    :param repo: Repository to generate data for
    :param suite: Suite to generate data for
    :param component: Component to generate data for
    :return:
    """

    mv_subq = (
        session.query(BinaryPackage.name, func.max(BinaryPackage.version).label('max_version'))
        .group_by(BinaryPackage.name)
        .subquery('t2')
    )

    # get the latest binary packages for this configuration
    bpkgs = (
        session.query(BinaryPackage)
        .join(
            mv_subq,
            and_(
                BinaryPackage.repo_id == repo.id,
                BinaryPackage.suites.any(id=suite.id),
                BinaryPackage.component_id == component.id,
                BinaryPackage.architecture_id == arch.id,
                BinaryPackage.version == mv_subq.c.max_version,
            ),
        )
        .order_by(BinaryPackage.name)
        .all()
    )

    entries = []
    for bpkg in bpkgs:
        # write sources file
        entry = Deb822()

        source_info = None
        if bpkg.name != bpkg.source.name:
            if bpkg.version == bpkg.source.version:
                source_info = bpkg.source.name
            else:
                source_info = bpkg.source.name + ' (' + bpkg.source.version + ')'

        set_deb822_value(entry, 'Package', bpkg.name)
        set_deb822_value(entry, 'Source', source_info)
        set_deb822_value(entry, 'Version', bpkg.version)
        set_deb822_value(entry, 'Maintainer', bpkg.maintainer)
        set_deb822_value(entry, 'Description', bpkg.summary)
        set_deb822_value(entry, 'Description-md5', bpkg.description_md5)
        set_deb822_value(entry, 'Homepage', bpkg.homepage)
        set_deb822_value(entry, 'Architecture', arch.name)
        set_deb822_value(entry, 'Multi-Arch', bpkg.multi_arch)
        set_deb822_value(entry, 'Section', bpkg.override.section.name)
        set_deb822_value(entry, 'Priority', packagepriority_to_string(bpkg.override.priority))
        set_deb822_value(entry, 'Pre-Depends', ', '.join(bpkg.pre_depends))
        set_deb822_value(entry, 'Depends', ', '.join(bpkg.depends))
        set_deb822_value(entry, 'Replaces', ', '.join(bpkg.replaces))
        set_deb822_value(entry, 'Provides', ', '.join(bpkg.provides))
        set_deb822_value(entry, 'Recommends', ', '.join(bpkg.recommends))
        set_deb822_value(entry, 'Suggests', ', '.join(bpkg.suggests))
        set_deb822_value(entry, 'Enhances', ', '.join(bpkg.enhances))
        set_deb822_value(entry, 'Conflicts', ', '.join(bpkg.conflicts))
        set_deb822_value(entry, 'Breaks', ', '.join(bpkg.breaks))
        set_deb822_value(entry, 'Built-Using', ', '.join(bpkg.built_using))
        set_deb822_value(entry, 'Installed-Size', str(bpkg.size_installed))
        set_deb822_value(entry, 'Filename', bpkg.bin_file.fname)
        set_deb822_value(entry, 'Size', str(bpkg.bin_file.size))
        set_deb822_value(entry, 'SHA256', bpkg.bin_file.sha256sum)
        if bpkg.phased_update_percentage < 100:
            set_deb822_value(entry, '"Phased-Update-Percentage"', str(bpkg.phased_update_percentage))

        for key, value in bpkg.extra_data.items():
            set_deb822_value(entry, key, value)

        entries.append(entry.dump())

    return '\n'.join(entries)


def publish_suite_dists(session, rss: ArchiveRepoSuiteSettings, *, force: bool = False):
    if not rss.changes_pending and not force:
        log.info('Not updating %s/%s: No pending changes.', rss.repo.name, rss.suite.name)
        return

    # global variables
    lconf = LocalConfig()
    archive_root_dir = lconf.archive_root_dir
    suite_dist_dir = os.path.join(archive_root_dir, rss.repo.name, 'dists', rss.suite.name)

    for component in rss.suite.components:
        suite_component_dists_dir = os.path.join(suite_dist_dir, component.name)

        # generate Sources
        res = generate_sources_index(session, rss.repo, rss.suite, component)
        print(res)

        # generate Packages
        for arch in rss.suite.architectures:
            res = generate_packages_index(session, rss.repo, rss.suite, component, arch)
            print(res)


def publish_repo_dists(session, repo: ArchiveRepository, *, force: bool = False):
    """
    Publish dists/ data for all (modified) suites in a repository.
    :param session:
    :param repo:
    :return:
    """

    for rss in repo.suite_settings:
        publish_suite_dists(session, rss, force=force)
