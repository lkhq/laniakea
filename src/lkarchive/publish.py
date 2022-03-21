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
from debian.deb822 import Deb822

from laniakea import LocalConfig
from laniakea.db import (
    ArchiveSuite,
    SourcePackage,
    ArchiveComponent,
    ArchiveRepository,
    ArchiveRepoSuiteSettings,
)
from laniakea.logging import log


def set_deb822_value(entry, key, value):
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

    spkgs = (
        session.query(SourcePackage)
        .filter(
            SourcePackage.repo_id == repo.id,
            SourcePackage.suites.any(id=suite.id),
            SourcePackage.component_id == component.id,
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


def publish_suite_dists(session, rss: ArchiveRepoSuiteSettings, *, force: bool = False):
    if not rss.changes_pending and not force:
        log.info('Not updating %s/%s: No pending changes.', rss.repo.name, rss.suite.name)
        return

    # global variables
    lconf = LocalConfig()
    archive_root_dir = lconf.archive_root_dir
    suite_dist_dir = os.path.join(archive_root_dir, rss.repo.name, 'dists', rss.suite.name)

    # generate Sources
    for component in rss.suite.components:
        suite_component_dists_dir = os.path.join(suite_dist_dir, component.name)

        res = generate_sources_index(session, rss.repo, rss.suite, component)
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
