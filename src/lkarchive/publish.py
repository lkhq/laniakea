# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import lzma
import shutil
import hashlib
import functools
from datetime import datetime, timedelta

from sqlalchemy import and_, func
from debian.deb822 import Deb822

import laniakea.typing as T
import laniakea.utils.renameat2 as renameat2
from laniakea import LocalConfig
from laniakea.db import (
    ArchiveSuite,
    BinaryPackage,
    SourcePackage,
    ArchiveComponent,
    ArchiveRepository,
    ArchiveArchitecture,
    ArchiveRepoSuiteSettings,
)
from laniakea.utils import process_file_lock, datetime_to_rfc2822_string
from laniakea.logging import log
from laniakea.utils.gpg import sign


@functools.total_ordering
class RepoFileInfo:
    def __init__(self, fname: T.PathUnion, size: int, sha256sum: str):
        self.fname = fname
        self.size = size
        self.sha256sum = sha256sum

    def __lt__(self, other):
        return self.fname < other.fname

    def __eq__(self, other):
        return self.fname == other.fname


def set_deb822_value(entry: Deb822, key: str, value: str):
    if value:
        entry[key] = value


def write_compressed_files(root_path: T.PathUnion, subdir: str, basename: str, data: str) -> T.List[RepoFileInfo]:
    """
    Write archive metadata file and compress it with all supported / applicable
    algorithms. Currently, we only support LZMA.
    :param root_path: Root directory of the repository.
    :param subdir: Subdirectory within the repository.
    :param basename: Base name of the metadata file, e.g. "Packages"
    :param data: Data the file should contain (usually UTF-8 text)
    """

    finfos = []
    data_bytes = data.encode('utf-8')
    repo_fname = os.path.join(subdir, basename)
    finfos.append(RepoFileInfo(repo_fname, len(data_bytes), hashlib.sha256(data_bytes).hexdigest()))

    fname_xz = os.path.join(root_path, repo_fname + '.xz')
    with lzma.open(fname_xz, 'w') as f:
        f.write(data_bytes)
    with open(fname_xz, 'rb') as f:
        xz_bytes = f.read()
        finfos.append(RepoFileInfo(repo_fname + '.xz', len(xz_bytes), hashlib.sha256(xz_bytes).hexdigest()))

    return finfos


def write_release_file_for_arch(
    root_path: T.PathUnion, subdir: str, rss: ArchiveRepoSuiteSettings, component: ArchiveComponent, arch_name: str
) -> RepoFileInfo:
    """
    Write Release data to the selected path based on information from :param rss
    """

    entry = Deb822()
    set_deb822_value(entry, 'Origin', rss.repo.origin_name)
    set_deb822_value(entry, 'Archive', rss.suite.name)
    set_deb822_value(entry, 'Version', rss.suite.version)
    set_deb822_value(entry, 'Component', component.name)
    entry['Architecture'] = arch_name

    with open(os.path.join(root_path, subdir, 'Release'), 'wb') as f:
        data = entry.dump().encode('utf-8')
        finfo = RepoFileInfo(os.path.join(subdir, 'Release'), len(data), hashlib.sha256(data).hexdigest())
        f.write(data)
    return finfo


def generate_sources_index(session, repo: ArchiveRepository, suite: ArchiveSuite, component: ArchiveComponent) -> str:
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
        .subquery()
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
) -> str:
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
        .subquery()
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
    i18n_entries = []
    for bpkg in bpkgs:
        # write sources file
        entry = Deb822()

        source_info = None
        if bpkg.name != bpkg.source.name:
            if bpkg.version == bpkg.source.version:
                source_info = bpkg.source.name
            else:
                source_info = bpkg.source.name + ' (' + bpkg.source.version + ')'

        entry['Package'] = bpkg.name
        set_deb822_value(entry, 'Source', source_info)
        set_deb822_value(entry, 'Version', bpkg.version)
        set_deb822_value(entry, 'Maintainer', bpkg.maintainer)
        set_deb822_value(entry, 'Description', bpkg.summary)
        set_deb822_value(entry, 'Description-md5', bpkg.description_md5)
        set_deb822_value(entry, 'Homepage', bpkg.homepage)
        set_deb822_value(entry, 'Architecture', arch.name)
        set_deb822_value(entry, 'Multi-Arch', bpkg.multi_arch)
        set_deb822_value(entry, 'Section', bpkg.override.section.name)
        set_deb822_value(entry, 'Priority', str(bpkg.override.priority))
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
        set_deb822_value(entry, 'Size', str(bpkg.bin_file.size))
        set_deb822_value(entry, 'Filename', bpkg.bin_file.fname)
        set_deb822_value(entry, 'SHA256', bpkg.bin_file.sha256sum)
        if bpkg.phased_update_percentage < 100:
            set_deb822_value(entry, '"Phased-Update-Percentage"', str(bpkg.phased_update_percentage))

        for key, value in bpkg.extra_data.items():
            set_deb822_value(entry, key, value)

        # add package metadata
        entries.append(entry.dump())

    return '\n'.join(entries)


def generate_i18n_template_data(
    session, repo: ArchiveRepository, suite: ArchiveSuite, component: ArchiveComponent
) -> str:
    """
     Generate i18n translation template data for the given repo/suite/component.
    :param session: Active SQLAlchemy session
    :param repo: Repository to generate data for
    :param suite: Suite to generate data for
    :param component: Component to generate data for
    :return:
    """

    mv_subq = (
        session.query(BinaryPackage.name, func.max(BinaryPackage.version).label('max_version'))
        .group_by(BinaryPackage.name)
        .subquery()
    )

    # get the latest binary packages, ignoring the architecture (so we will select only one at random)
    # TODO: We can radically simplify this with a deducated SQL query that doesn't fetch the whole BinaryPackage object
    bpkgs = (
        session.query(BinaryPackage)
        .join(
            mv_subq,
            and_(
                BinaryPackage.repo_id == repo.id,
                BinaryPackage.suites.any(id=suite.id),
                BinaryPackage.component_id == component.id,
                BinaryPackage.version == mv_subq.c.max_version,
            ),
        )
        .order_by(BinaryPackage.name)
        .distinct(BinaryPackage.name)
    )

    i18n_entries = []
    for bpkg in bpkgs:
        i18n_entry = Deb822()
        i18n_entry['Package'] = bpkg.name
        i18n_entry['Description-md5'] = bpkg.description_md5
        i18n_entry['Description-en'] = bpkg.description
        i18n_entries.append(i18n_entry.dump())

    return '\n'.join(i18n_entries)


def publish_suite_dists(session, rss: ArchiveRepoSuiteSettings, *, force: bool = False):
    if not rss.changes_pending and not force:
        log.info('Not updating %s/%s: No pending changes.', rss.repo.name, rss.suite.name)
        return

    # global variables
    lconf = LocalConfig()
    archive_root_dir = lconf.archive_root_dir
    repo_dists_dir = os.path.join(archive_root_dir, rss.repo.name, 'dists')
    temp_dists_dir = os.path.join(archive_root_dir, rss.repo.name, 'zzz-meta')
    suite_temp_dist_dir = os.path.join(temp_dists_dir, rss.suite.name)

    # remove possible remnants of an older publish operation
    if os.path.isdir(temp_dists_dir):
        shutil.rmtree(temp_dists_dir)

    # copy old directory tree to our temporary location for editing
    if os.path.isdir(repo_dists_dir):
        shutil.copytree(repo_dists_dir, temp_dists_dir, symlinks=True, ignore_dangling_symlinks=True)
    os.makedirs(suite_temp_dist_dir, exist_ok=True)

    # update metadata
    meta_files = []
    for component in rss.suite.components:
        dists_sources_subdir = os.path.join(component.name, 'source')
        suite_component_dists_sources_dir = os.path.join(suite_temp_dist_dir, dists_sources_subdir)
        os.makedirs(suite_component_dists_sources_dir, exist_ok=True)

        # generate Sources
        res = generate_sources_index(session, rss.repo, rss.suite, component)
        meta_files.extend(write_compressed_files(suite_temp_dist_dir, dists_sources_subdir, 'Sources', res))
        meta_files.append(
            write_release_file_for_arch(suite_temp_dist_dir, dists_sources_subdir, rss, component, 'source')
        )

        # generate Packages
        for arch in rss.suite.architectures:
            dists_arch_subdir = os.path.join(component.name, 'binary-' + arch.name)
            suite_component_dists_arch_dir = os.path.join(suite_temp_dist_dir, dists_arch_subdir)
            os.makedirs(suite_component_dists_arch_dir, exist_ok=True)

            pkg_data = generate_packages_index(session, rss.repo, rss.suite, component, arch)
            meta_files.extend(write_compressed_files(suite_temp_dist_dir, dists_arch_subdir, 'Packages', pkg_data))
            meta_files.append(
                write_release_file_for_arch(suite_temp_dist_dir, dists_arch_subdir, rss, component, arch.name)
            )

        # create i19n template data
        dists_i18n_subdir = os.path.join(component.name, 'i18n')
        suite_component_dists_i18n_dir = os.path.join(suite_temp_dist_dir, dists_i18n_subdir)
        os.makedirs(suite_component_dists_i18n_dir, exist_ok=True)
        i18n_data = generate_i18n_template_data(session, rss.repo, rss.suite, component)
        meta_files.extend(write_compressed_files(suite_temp_dist_dir, dists_i18n_subdir, 'Translation-en', i18n_data))

    # write root release file
    root_rel_fname = os.path.join(suite_temp_dist_dir, 'Release')
    entry = Deb822()
    set_deb822_value(entry, 'Origin', rss.repo.origin_name)
    set_deb822_value(entry, 'Suite', rss.suite.name)
    set_deb822_value(entry, 'Version', rss.suite.version)
    set_deb822_value(entry, 'Codename', rss.suite.alias)
    set_deb822_value(entry, 'Label', rss.suite.summary)
    entry['Date'] = datetime_to_rfc2822_string(datetime.now())
    entry['Valid-Until'] = datetime_to_rfc2822_string(datetime.now() + timedelta(days=7))
    entry['Acquire-By-Hash'] = 'no'  # FIXME: We need to implement this, then change this line to allow by-hash
    entry['Architectures'] = ' '.join(sorted([a.name for a in rss.suite.architectures]))
    entry['Components'] = ' '.join(sorted([c.name for c in rss.suite.components]))

    metafile_data = [f' {f.sha256sum} {f.size: >8} {f.fname}' for f in sorted(meta_files)]
    entry['SHA256'] = '\n' + '\n'.join(metafile_data)

    with open(os.path.join(root_rel_fname), 'w', encoding='utf-8') as f:
        f.write(entry.dump())

    # sign our changes
    root_relsigned_il_fname = os.path.join(suite_temp_dist_dir, 'InRelease')
    root_relsigned_dt_fname = os.path.join(suite_temp_dist_dir, 'Release.gpg')
    with open(root_rel_fname, 'rb') as rel_f:
        # inline signature
        with open(root_relsigned_il_fname, 'wb') as signed_f:
            sign(
                rel_f,
                signed_f,
                rss.signingkeys,
                inline=True,
                homedir=lconf.secret_gpg_home_dir,
            )
        # detached signature
        with open(root_relsigned_dt_fname, 'wb') as signed_f:
            sign(
                rel_f,
                signed_f,
                rss.signingkeys,
                inline=False,
                homedir=lconf.secret_gpg_home_dir,
            )

    # mark changes as live, atomically replace old location by swapping the paths,
    # then deleting the old one.
    if os.path.isdir(repo_dists_dir):
        renameat2.exchange_paths(temp_dists_dir, repo_dists_dir)
        shutil.rmtree(temp_dists_dir)
    else:
        os.rename(temp_dists_dir, repo_dists_dir)


def publish_repo_dists(session, repo: ArchiveRepository, *, force: bool = False):
    """
    Publish dists/ data for all (modified) suites in a repository.
    :param session:
    :param repo:
    :return:
    """

    with process_file_lock(repo.name):
        for rss in repo.suite_settings:
            publish_suite_dists(session, rss, force=force)
