# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import sys
import gzip
import lzma
import time
import shutil
import hashlib
import functools
import multiprocessing as mproc
from glob import iglob
from pathlib import Path
from datetime import datetime, timedelta

import click
from pebble import concurrent
from sqlalchemy import and_, func
from rich.console import Console
from debian.deb822 import Deb822
from sqlalchemy.orm import joinedload

import laniakea.typing as T
import laniakea.utils.renameat2 as renameat2
from laniakea import LocalConfig
from laniakea.db import (
    ArchiveSuite,
    BinaryPackage,
    SourcePackage,
    PackageOverride,
    ArchiveComponent,
    ArchiveRepository,
    ArchiveArchitecture,
    ArchiveRepoSuiteSettings,
    session_scope,
)
from laniakea.utils import (
    hardlink_or_copy,
    process_file_lock,
    datetime_to_rfc2822_string,
)
from laniakea.archive import repo_suite_settings_for
from laniakea.logging import log, archive_log
from laniakea.utils.gpg import sign
from laniakea.archive.appstream import import_appstream_data


class ArchivePublishError(Exception):
    """Something went wrong while publishing a repository."""


@concurrent.process(daemon=False, name='dep11-import', context=mproc.get_context('forkserver'))
def _retrieve_dep11_data_async(
    repo_name: str, lconf_fname: T.Optional[T.PathUnion] = None
) -> T.Tuple[bool, T.Optional[str], T.Optional[T.PathUnion]]:
    """Fetch DEP-11 data from an external source
    This will fetch the AppStream/DEP-11 data via a hook script, validate it
    and move it to its destination.
    """
    import subprocess

    from laniakea.logging import configure_pkg_archive_logger
    from lkarchive.check_dep11 import check_dep11_path

    # reload singleton data for multiprocessing
    lconf = LocalConfig(lconf_fname)
    # reconfigure logging
    configure_pkg_archive_logger()

    hook_script = os.path.join(lconf.data_import_hooks_dir, 'fetch-appstream.sh')
    if not os.path.isfile(hook_script):
        log.info('Will not fetch DEP-11 data for %s: No hook script `%s`', repo_name, hook_script)
        return True, None, None

    dep11_tmp_target = os.path.join(lconf.cache_dir, 'import_dep11-' + repo_name)
    if os.path.isdir(dep11_tmp_target):
        shutil.rmtree(dep11_tmp_target)
    os.makedirs(dep11_tmp_target, exist_ok=True)
    env = os.environ
    env['LK_DATA_TARGET_DIR'] = dep11_tmp_target
    env['LK_REPO_NAME'] = repo_name
    proc = subprocess.run(hook_script, check=False, capture_output=True, cwd=dep11_tmp_target, env=env)
    if proc.returncode != 0:
        return False, 'Hook script failed: {}{}'.format(str(proc.stdout, 'utf-8'), str(proc.stderr, 'utf-8')), None

    if not any(os.scandir(dep11_tmp_target)):
        log.debug('No DEP-11 data received for repository %s', repo_name)
        return True, None, None

    log.info('Validating received DEP-11 metadata for %s', repo_name)
    success, issues = check_dep11_path(dep11_tmp_target)
    if not success:
        return False, 'DEP11 validation failed:\n' + '\n'.join(issues), None

    # everything went fine, we can use this data (if there is any)
    return True, None, dep11_tmp_target


@functools.total_ordering
class RepoFileInfo:
    def __init__(self, fname: T.PathUnion, size: int, checksum_name: str, checksum: str):
        self.fname = fname
        self.size = size
        self.checksum_name = checksum_name
        self.checksum = checksum
        assert self.checksum_name == 'MD5Sum' or self.checksum_name == 'SHA256'

    def __lt__(self, other):
        return self.fname < other.fname

    def __eq__(self, other):
        return self.fname == other.fname


def set_deb822_value(entry: Deb822, key: str, value: T.Optional[str]):
    """Optionally set a DEB822 string value."""
    if value:
        entry[key] = value


def set_deb822_value_commalist(entry: Deb822, key: str, value: T.Optional[T.Iterable[str]]):
    """Optionally set a DEB822 value and format it as comma-separated list"""
    if value:
        entry[key] = ', '.join(value)


def set_deb822_value_spacelist(entry: Deb822, key: str, value: T.Optional[T.Iterable[str]]):
    """Optionally set a DEB822 value and format it as space-separated list"""
    if value:
        entry[key] = ' '.join(value)


def create_by_hash_for(
    root_path: T.PathUnion, repo_fname: T.PathUnion, component: ArchiveComponent | str
) -> list[RepoFileInfo]:
    """Write a by-hash file into the appropriate location, replacing the original with a symlink.

    :param root_path: Root subdirectory in dists/ where the components folders are located.
    :param repo_fname: The location below root_path for this file.
    :param component: The component we are working on.

    :return: List of generated RepoFileInfo for the selected hashes and source file.
    """

    component_name = component if isinstance(component, str) else component.name
    by_hash_root = os.path.join(root_path, component_name, 'by-hash')
    by_hash_md5_root = os.path.join(by_hash_root, 'MD5Sum')
    by_hash_sha256_root = os.path.join(by_hash_root, 'SHA256')
    os.makedirs(by_hash_md5_root, exist_ok=True)
    os.makedirs(by_hash_sha256_root, exist_ok=True)

    fname_full = os.path.join(root_path, repo_fname)
    with open(fname_full, 'rb') as f:
        data = f.read()

    sha256_digest = hashlib.sha256(data).hexdigest()
    md5_digest = hashlib.md5(data).hexdigest()
    finfos = [
        RepoFileInfo(repo_fname, len(data), 'SHA256', sha256_digest),
        RepoFileInfo(repo_fname, len(data), 'MD5Sum', md5_digest),
    ]

    # We could use hardlinks here, but if the source file is written to directly, the by-hash files
    # would change, which we want to avoid at all costs. So instead, we use deep copies here.
    sha256_fname = os.path.join(by_hash_sha256_root, str(sha256_digest))
    # replace original with symlink
    os.rename(fname_full, sha256_fname)
    os.symlink(os.path.relpath(sha256_fname, os.path.join(fname_full, '..')), fname_full)

    # hardlink other aliases
    hardlink_or_copy(sha256_fname, os.path.join(by_hash_md5_root, str(md5_digest)), override=True)

    return finfos


def write_compressed_files(
    root_path: T.PathUnion,
    subdir: str,
    basename: str,
    *,
    component: T.Optional[ArchiveComponent | str] = None,
    data: str,
) -> T.List[RepoFileInfo]:
    """
    Write archive metadata file and compress it with all supported / applicable
    algorithms. Currently, we only support LZMA.
    :param root_path: Root directory of the repository.
    :param subdir: Subdirectory within the repository.
    :param basename: Base name of the metadata file, e.g. "Packages"
    :param component: Archive component to write data into
    :param data: Data the file should contain (usually UTF-8 text)
    """

    if not component:
        component_name = ''
    else:
        component_name = component if isinstance(component, str) else component.name

    finfos = []
    data_bytes = data.encode('utf-8')
    repo_fname = os.path.join(component_name, subdir, basename)

    # uncompressed checksums
    finfos.append(RepoFileInfo(repo_fname, len(data_bytes), 'SHA256', hashlib.sha256(data_bytes).hexdigest()))
    finfos.append(RepoFileInfo(repo_fname, len(data_bytes), 'MD5Sum', hashlib.md5(data_bytes).hexdigest()))

    # write compressed data
    fname_xz = os.path.join(root_path, repo_fname + '.xz')
    if os.path.islink(fname_xz):
        os.unlink(fname_xz)
    with lzma.open(fname_xz, 'w') as f:
        f.write(data_bytes)

    # write by-hash data and finish
    finfos.extend(create_by_hash_for(root_path, repo_fname + '.xz', component=component))
    return finfos


def import_metadata_file(
    root_path: T.PathUnion,
    subdir: str,
    basename: str,
    source_fname: T.PathUnion,
    component: ArchiveComponent | str,
    *,
    only_compression: T.Optional[str] = None,
) -> T.List[RepoFileInfo]:
    """
    Import a metadata file from a source, checksum it and (re)compress it with all supported / applicable
    algorithms.
    :param root_path: Root directory of the repository.
    :param subdir: Subdirectory within the repository.
    :param basename: Base name of the metadata file, e.g. "Packages"
    :param source_fname: The source file to import.
    :param component: The component to import into.
    """

    source_fname = str(source_fname)

    finfos = []
    if source_fname.endswith('.xz'):
        with lzma.open(source_fname, 'rb') as f:
            data = f.read()
    elif source_fname.endswith('.gz'):
        with gzip.open(source_fname, 'rb') as f:
            data = f.read()
    else:
        with open(source_fname, 'rb') as f:
            data = f.read()
    repo_fname = os.path.join(subdir, basename)

    # add uncompressed checksums
    data_md5 = hashlib.md5(data).hexdigest()
    data_sha256 = hashlib.sha256(data).hexdigest()
    finfos.append(RepoFileInfo(repo_fname, len(data), 'SHA256', data_sha256))
    finfos.append(RepoFileInfo(repo_fname, len(data), 'MD5Sum', data_md5))

    # comp_root_dir = os.path.normpath(os.path.join(root_path, '..'))
    if only_compression:
        use_exts = [only_compression]
    else:
        use_exts = ['xz', 'gz']

    for z_ext in use_exts:
        repo_fname_comp = repo_fname + '.' + z_ext
        fname_z = os.path.join(root_path, repo_fname_comp)
        if os.path.islink(fname_z):
            os.unlink(fname_z)
        if z_ext == 'gz':
            with gzip.open(fname_z, 'w') as f:
                f.write(data)
        elif z_ext == 'xz':
            with lzma.open(fname_z, 'w') as f:
                f.write(data)
        else:
            raise Exception('Unknown compressed file extension: ' + z_ext)

        # make by-hash data
        finfos.extend(create_by_hash_for(root_path, repo_fname_comp, component=component))

    return finfos


def write_release_file_for_arch(
    root_path: T.PathUnion, subdir: str, rss: ArchiveRepoSuiteSettings, component: ArchiveComponent, arch_name: str
) -> T.List[RepoFileInfo]:
    """
    Write Release data to the selected path based on information from :param rss
    """

    entry = Deb822()
    set_deb822_value(entry, 'Origin', rss.repo.origin_name)
    set_deb822_value(entry, 'Archive', rss.suite.name)
    set_deb822_value(entry, 'Version', rss.suite.version)
    set_deb822_value(entry, 'Component', component.name)
    entry['Architecture'] = arch_name

    finfos = []
    release_name = os.path.join(component.name, subdir, 'Release')
    release_path_full = os.path.join(root_path, release_name)
    if os.path.islink(release_path_full):
        os.unlink(release_path_full)
    with open(release_path_full, 'wb') as f:
        data = entry.dump().encode('utf-8')
        f.write(data)

    finfos.extend(create_by_hash_for(root_path, release_name, component=component))
    return finfos


def generate_sources_index(session, repo: ArchiveRepository, suite: ArchiveSuite, component: ArchiveComponent) -> str:
    """
    Generate Sources index data for the given repo/suite/component.
    :param session: Active SQLAlchemy session
    :param repo: Repository to generate data for
    :param suite: Suite to generate data for
    :param component: Component to generate data for
    :return:
    """

    spkg_filters = [
        SourcePackage.repo_id == repo.id,
        SourcePackage.suites.any(id=suite.id),
        SourcePackage.component_id == component.id,
        SourcePackage.time_deleted.is_(None),
    ]

    spkg_filter_sq = session.query(SourcePackage).filter(*spkg_filters).subquery()
    smv_sq = (
        session.query(spkg_filter_sq.c.name, func.max(spkg_filter_sq.c.version).label('max_version'))
        .group_by(spkg_filter_sq.c.name)
        .subquery('smv_sq')
    )

    # get the latest source packages for this configuration
    spkgs = (
        session.query(SourcePackage)
        .options(joinedload(SourcePackage.section), joinedload(SourcePackage.files))
        .filter(*spkg_filters)
        .join(
            smv_sq,
            and_(
                SourcePackage.name == smv_sq.c.name,
                SourcePackage.version == smv_sq.c.max_version,
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
        set_deb822_value_commalist(entry, 'Uploaders', spkg.uploaders)

        set_deb822_value_spacelist(entry, 'Architecture', spkg.architectures)
        set_deb822_value(entry, 'Format', spkg.format_version)
        set_deb822_value(entry, 'Standards-Version', spkg.standards_version)

        set_deb822_value(entry, 'Section', spkg.section.name)
        set_deb822_value(entry, 'Homepage', spkg.homepage)
        set_deb822_value(entry, 'Vcs-Browser', spkg.vcs_browser)
        set_deb822_value(entry, 'Vcs-Git', spkg.vcs_git)

        set_deb822_value_commalist(entry, 'Build-Depends', spkg.build_depends)
        set_deb822_value_commalist(entry, 'Build-Depends-Indep', spkg.build_depends_indep)
        set_deb822_value_commalist(entry, 'Build-Depends-Arch', spkg.build_depends_arch)
        set_deb822_value_commalist(entry, 'Build-Conflicts', spkg.build_conflicts)
        set_deb822_value_commalist(entry, 'Build-Conflicts-Indep', spkg.build_conflicts_indep)
        set_deb822_value_commalist(entry, 'Build-Conflicts-Arch', spkg.build_conflicts_arch)

        set_deb822_value_commalist(entry, 'Testsuite', spkg.testsuite)
        set_deb822_value_commalist(entry, 'Testsuite-Triggers', spkg.testsuite_triggers)

        set_deb822_value(entry, 'Directory', spkg.directory)
        cs_data = []
        for file in spkg.files:
            cs_data.append('{} {} {}'.format(file.sha256sum, file.size, file.fname))
        set_deb822_value(entry, 'Checksums-Sha256', '\n ' + '\n '.join(cs_data))

        extra_data = spkg.extra_data
        if extra_data:
            for key, value in extra_data.items():
                set_deb822_value(entry, key, value)

        entries.append(entry.dump())

    return '\n'.join(entries)


def generate_packages_index(
    session,
    repo: ArchiveRepository,
    suite: ArchiveSuite,
    component: ArchiveComponent,
    arch: ArchiveArchitecture,
    *,
    installer_udeb: bool = False,
) -> str:
    """
    Generate Packages index data for the given repo/suite/component/arch.
    :param session: Active SQLAlchemy session
    :param repo: Repository to generate data for
    :param suite: Suite to generate data for
    :param component: Component to generate data for
    :param installer_udeb: True if we should build the debian-installer index
    :return:
    """

    from laniakea.db.archive import DebType

    rss = (
        session.query(ArchiveRepoSuiteSettings)
        .filter(
            ArchiveRepoSuiteSettings.repo_id == repo.id,
            ArchiveRepoSuiteSettings.suite_id == suite.id,
        )
        .one()
    )

    deb_type = DebType.DEB
    if installer_udeb:
        deb_type = DebType.UDEB

    bpkg_filter = [
        BinaryPackage.deb_type == deb_type,
        BinaryPackage.repo_id == repo.id,
        BinaryPackage.suites.any(id=suite.id),
        BinaryPackage.component_id == component.id,
        BinaryPackage.architecture_id == arch.id,
        BinaryPackage.time_deleted.is_(None),
    ]

    bpkg_filter_sq = session.query(BinaryPackage).filter(*bpkg_filter).subquery()
    bmv_sq = (
        session.query(bpkg_filter_sq.c.name, func.max(bpkg_filter_sq.c.version).label('max_version'))
        .group_by(bpkg_filter_sq.c.name)
        .subquery('bmv_sq')
    )

    # get the latest binary packages for this configuration
    bpkgs_overrides = (
        session.query(BinaryPackage, PackageOverride)
        .options(joinedload(BinaryPackage.bin_file), joinedload(PackageOverride.section))
        .join(
            bmv_sq,
            and_(
                BinaryPackage.name == bmv_sq.c.name,
                BinaryPackage.version == bmv_sq.c.max_version,
            ),
        )
        .join(
            PackageOverride,
            and_(
                PackageOverride.repo_id == rss.repo_id,
                PackageOverride.suite_id == rss.suite_id,
                BinaryPackage.name == PackageOverride.pkg_name,
            ),
        )
        .filter(*bpkg_filter)
        .order_by(BinaryPackage.name)
        .all()
    )

    entries = []
    for bpkg, bpkg_override in bpkgs_overrides:
        # write sources file
        entry = Deb822()

        source_info = None
        bpkg_is_binmu = bpkg.version != bpkg.source.version
        if bpkg_is_binmu or bpkg.name != bpkg.source.name:
            if bpkg_is_binmu:
                source_info = bpkg.source.name + ' (' + bpkg.source.version + ')'
            else:
                source_info = bpkg.source.name

        entry['Package'] = bpkg.name
        set_deb822_value(entry, 'Source', source_info)
        set_deb822_value(entry, 'Version', bpkg.version)
        if bpkg_override.essential:
            set_deb822_value(entry, 'Essential', 'yes')
        set_deb822_value(entry, 'Maintainer', bpkg.maintainer)
        set_deb822_value(entry, 'Original-Maintainer', bpkg.original_maintainer)
        set_deb822_value(entry, 'Description', bpkg.summary)
        set_deb822_value(entry, 'Description-md5', bpkg.description_md5)
        set_deb822_value(entry, 'Homepage', bpkg.homepage)
        set_deb822_value(entry, 'Architecture', arch.name)
        set_deb822_value(entry, 'Multi-Arch', bpkg.multi_arch)
        set_deb822_value(entry, 'Section', bpkg_override.section.name)
        set_deb822_value(entry, 'Priority', str(bpkg_override.priority))
        set_deb822_value_commalist(entry, 'Pre-Depends', bpkg.pre_depends)
        set_deb822_value_commalist(entry, 'Depends', bpkg.depends)
        set_deb822_value_commalist(entry, 'Replaces', bpkg.replaces)
        set_deb822_value_commalist(entry, 'Provides', bpkg.provides)
        set_deb822_value_commalist(entry, 'Recommends', bpkg.recommends)
        set_deb822_value_commalist(entry, 'Suggests', bpkg.suggests)
        set_deb822_value_commalist(entry, 'Enhances', bpkg.enhances)
        set_deb822_value_commalist(entry, 'Conflicts', bpkg.conflicts)
        set_deb822_value_commalist(entry, 'Breaks', bpkg.breaks)
        set_deb822_value_commalist(entry, 'Built-Using', bpkg.built_using)
        set_deb822_value_commalist(entry, 'Static-Built-Using', bpkg.static_built_using)
        set_deb822_value_spacelist(entry, 'Build-Ids', bpkg.build_ids)

        if bpkg.size_installed > 0:
            set_deb822_value(entry, 'Installed-Size', str(bpkg.size_installed))
        set_deb822_value(entry, 'Size', str(bpkg.bin_file.size))
        set_deb822_value(entry, 'Filename', bpkg.bin_file.fname)
        set_deb822_value(entry, 'SHA256', bpkg.bin_file.sha256sum)
        if bpkg.phased_update_percentage < 100:
            set_deb822_value(entry, '"Phased-Update-Percentage"', str(bpkg.phased_update_percentage))

        extra_data = bpkg.extra_data
        if extra_data:
            for key, value in extra_data.items():
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

    bpkg_filters = [
        BinaryPackage.repo_id == repo.id,
        BinaryPackage.suites.any(id=suite.id),
        BinaryPackage.component_id == component.id,
        BinaryPackage.time_deleted.is_(None),
    ]

    bpkg_filter_sq = session.query(BinaryPackage).filter(*bpkg_filters).subquery()
    bmv_sq = (
        session.query(bpkg_filter_sq.c.name, func.max(bpkg_filter_sq.c.version).label('max_version'))
        .group_by(bpkg_filter_sq.c.name)
        .subquery('bmv_sq')
    )

    # get the latest binary packages, ignoring the architecture (so we will select only one at random)
    i18n_data = (
        session.query(BinaryPackage.name, BinaryPackage.description_md5, BinaryPackage.description)
        .filter(*bpkg_filters)
        .join(
            bmv_sq,
            and_(
                BinaryPackage.name == bmv_sq.c.name,
                BinaryPackage.version == bmv_sq.c.max_version,
            ),
        )
        .order_by(BinaryPackage.name)
        .distinct(BinaryPackage.name)
        .all()
    )

    i18n_entries = []
    for pkgname, description_md5, description in i18n_data:
        i18n_entry = Deb822()
        i18n_entry['Package'] = pkgname
        i18n_entry['Description-md5'] = description_md5
        i18n_entry['Description-en'] = description
        i18n_entries.append(i18n_entry.dump())

    return '\n'.join(i18n_entries)


def _expire_by_hash_files(root_path: T.PathUnion, component: ArchiveComponent, meta_files: list[RepoFileInfo]) -> None:
    """
    Expire obsolete files in by-hash directories.
    :param root_path: Root part to the archive metadata directory.
    :param component: Archive component to act on.
    :return:
    """

    active_cs = set()
    for fi in meta_files:
        active_cs.add(str(fi.checksum))

    comp_root_path = os.path.join(root_path, component.name)
    by_hash_root = os.path.join(comp_root_path, 'by-hash')
    if not os.path.isdir(by_hash_root):
        log.error('Expected by-hash dir is missing: %s', by_hash_root)
        return

    two_weeks_ago = time.time() - (14 * 24 * 60 * 60)
    for path, _, files in os.walk(by_hash_root):
        for file in files:
            # we do nothing to a hash file if it is actively referenced
            if file in active_cs:
                continue

            fname = os.path.join(path, file)
            ti_m = os.path.getmtime(fname)
            if ti_m < two_weeks_ago:
                log.debug('Deleting obsolete by-hash file: %s', fname)
                os.unlink(fname)


def _ensure_byhash_compat_link(component_arch_subdir_full: T.PathUnion):
    """Ensure a by-hash compat symlink exists in an arch-specific directory of a component."""
    byhash_dir_link = os.path.join(component_arch_subdir_full, 'by-hash')
    if os.path.islink(byhash_dir_link):
        return

    if os.path.exists(byhash_dir_link):
        shutil.rmtree(byhash_dir_link)
    os.symlink(os.path.join('..', 'by-hash'), byhash_dir_link)


def _publish_suite_dists(
    lconf: LocalConfig,
    session,
    rss: ArchiveRepoSuiteSettings,
    *,
    dep11_src_dir: T.Optional[T.PathUnion],
    only_sources: bool = False,
    force: bool = False,
):
    # we must never touch a frozen suite
    if rss.frozen:
        log.debug('Not publishing frozen suite %s/%s', rss.repo.name, rss.suite.name)
        return

    # update the suite data if forced, explicitly marked as changes pending or if we published the suite
    # for the last time about a week ago (6 days to give admins some time to fix issues before the old
    # data expires about 2 days later)
    if not rss.changes_pending and not force and not rss.time_published < datetime.utcnow() - timedelta(days=6):
        log.info('Not updating %s/%s: No pending changes.', rss.repo.name, rss.suite.name)
        return

    if only_sources:
        log.info('Publishing only Sources index for suite: %s/%s', rss.repo.name, rss.suite.name)
    else:
        log.info('Publishing suite: %s/%s', rss.repo.name, rss.suite.name)

    # global settings
    archive_root_dir = lconf.archive_root_dir
    temp_dists_root = os.path.join(archive_root_dir, rss.repo.name, 'zzz-meta')
    repo_dists_root = os.path.join(archive_root_dir, rss.repo.name, 'dists')
    suite_temp_dist_dir = os.path.join(temp_dists_root, rss.suite.name)
    suite_repo_dist_dir = os.path.join(repo_dists_root, rss.suite.name)

    # copy old directory tree to our temporary location for editing
    if os.path.isdir(suite_repo_dist_dir):
        shutil.copytree(suite_repo_dist_dir, suite_temp_dist_dir, symlinks=True, ignore_dangling_symlinks=True)
    os.makedirs(suite_temp_dist_dir, exist_ok=True)
    os.makedirs(repo_dists_root, exist_ok=True)

    # sanity check
    root_rel_fname = os.path.join(suite_temp_dist_dir, 'Release')
    if only_sources and not os.path.isfile(root_rel_fname):
        raise ArchivePublishError(
            'Can not update only sources, since "{}/{}" has never once been fully published.'.format(
                rss.repo.name, rss.suite.name
            )
        )

    # update metadata
    meta_files: list[RepoFileInfo] = []
    for component in rss.suite.components:
        suite_component_dists_sources_dir = os.path.join(suite_temp_dist_dir, component.name, 'source')
        os.makedirs(suite_component_dists_sources_dir, exist_ok=True)

        # create link in directory pointing to the shared by-hash folder for compatibility
        _ensure_byhash_compat_link(suite_component_dists_sources_dir)

        # generate Sources
        res = generate_sources_index(session, rss.repo, rss.suite, component)
        meta_files.extend(
            write_compressed_files(suite_temp_dist_dir, 'source', 'Sources', component=component, data=res)
        )
        meta_files.extend(write_release_file_for_arch(suite_temp_dist_dir, 'source', rss, component, 'source'))

        # don't write anything else if we only need to update the Sources index
        if only_sources:
            continue

        dists_dep11_subdir = os.path.join(component.name, 'dep11')
        for arch in rss.suite.architectures:
            # generate Packages
            dists_arch_subdir = 'binary-' + arch.name
            suite_component_dists_arch_dir_full = os.path.join(suite_temp_dist_dir, component.name, dists_arch_subdir)
            os.makedirs(suite_component_dists_arch_dir_full, exist_ok=True)

            # create link in directory pointing to the shared by-hash folder for compatibility
            _ensure_byhash_compat_link(suite_component_dists_arch_dir_full)

            pkg_data = generate_packages_index(session, rss.repo, rss.suite, component, arch, installer_udeb=False)
            meta_files.extend(
                write_compressed_files(
                    suite_temp_dist_dir, dists_arch_subdir, 'Packages', component=component, data=pkg_data
                )
            )
            meta_files.extend(
                write_release_file_for_arch(suite_temp_dist_dir, dists_arch_subdir, rss, component, arch.name)
            )

            # only add debian-installer data if we are not a debug suite
            if not rss.suite.debug_suite_for:
                dists_arch_di_subdir = os.path.join('debian-installer', 'binary-' + arch.name)
                os.makedirs(
                    os.path.join(suite_temp_dist_dir, os.path.join(component.name, dists_arch_di_subdir)), exist_ok=True
                )
                pkg_data_di = generate_packages_index(
                    session, rss.repo, rss.suite, component, arch, installer_udeb=True
                )
                meta_files.extend(
                    write_compressed_files(
                        suite_temp_dist_dir, dists_arch_di_subdir, 'Packages', component=component, data=pkg_data_di
                    )
                )

            # import AppStream data
            if dep11_src_dir:
                dep11_files = ('Components-{}.yml'.format(arch.name), 'CID-Index-{}.json'.format(arch.name))
                for dep11_basename in dep11_files:
                    for ext in ('.gz', '.xz'):
                        dep11_src_fname = os.path.join(
                            dep11_src_dir, rss.suite.name, component.name, dep11_basename + ext
                        )
                        if os.path.isfile(dep11_src_fname):
                            break
                    if not os.path.isfile(dep11_src_fname):
                        continue
                    os.makedirs(os.path.join(suite_temp_dist_dir, dists_dep11_subdir), exist_ok=True)

                    # copy metadata, hash and register it
                    meta_files.extend(
                        import_metadata_file(
                            suite_temp_dist_dir,
                            dists_dep11_subdir,
                            dep11_basename,
                            dep11_src_fname,
                            component,
                            only_compression='xz' if dep11_basename.startswith('CID-Index') else None,
                        )
                    )

                # import metadata into the database and connect it to binary packages
                import_appstream_data(session, rss, component, arch, repo_dists_dir=temp_dists_root)

        # copy AppStream icon tarballs
        if dep11_src_dir and not only_sources:
            dep11_suite_component_src_dir = os.path.join(dep11_src_dir, rss.suite.name, component.name)
            for icon_tar_fname in iglob(os.path.join(dep11_suite_component_src_dir, 'icons-*.tar.gz')):
                icon_tar_fname = os.path.join(dep11_suite_component_src_dir, icon_tar_fname)
                meta_files.extend(
                    import_metadata_file(
                        suite_temp_dist_dir,
                        dists_dep11_subdir,
                        Path(icon_tar_fname).stem,
                        icon_tar_fname,
                        component,
                        only_compression='gz',
                    )
                )

        # create i19n template data
        if not only_sources:
            suite_component_dists_i18n_dir = os.path.join(suite_temp_dist_dir, component.name, 'i18n')
            os.makedirs(suite_component_dists_i18n_dir, exist_ok=True)
            i18n_data = generate_i18n_template_data(session, rss.repo, rss.suite, component)
            meta_files.extend(
                write_compressed_files(
                    suite_temp_dist_dir, 'i18n', 'Translation-en', component=component, data=i18n_data
                )
            )

        if not only_sources:
            # expire old by-hash files
            _expire_by_hash_files(suite_temp_dist_dir, component, meta_files)

    # write root release file
    if only_sources:
        # if we are in "only sources" update mode, we patch the existing file instead of writing a new one
        with open(root_rel_fname, 'r', encoding='utf-8') as f:
            entry = Deb822(f)
    else:
        entry = Deb822()

    suite_codename = rss.suite.alias
    if rss.suite.name.startswith('byzantium'):
        # FIXME: HACK: This is a dirty hack to aid the migration of PureOS' systems to the new version of Laniakea.
        # Dak previously put "None" (as string) for an unset value here, which we don't want to do. We also can not
        # set the suite alias to "None", since that would violate the duplicate key constraint of the database, since
        # suites like byzantium-security would have the same "None" codename.
        # So for simplicity, we have this dirty hack implemented here, until the byzantium suite can be dropped
        # in the far future.
        suite_codename = 'None'
    elif not suite_codename:
        suite_codename = rss.suite.name

    set_deb822_value(entry, 'Origin', rss.repo.origin_name)
    set_deb822_value(entry, 'Suite', rss.suite.name)
    set_deb822_value(entry, 'Version', rss.suite.version)
    set_deb822_value(entry, 'Codename', suite_codename)
    set_deb822_value(entry, 'Label', rss.suite.summary)
    entry['Date'] = datetime_to_rfc2822_string(datetime.utcnow())
    if not rss.frozen and not only_sources:
        entry['Valid-Until'] = datetime_to_rfc2822_string(datetime.utcnow() + timedelta(days=8))
    entry['Acquire-By-Hash'] = 'yes'
    entry['Architectures'] = ' '.join(sorted([a.name for a in rss.suite.architectures]))
    entry['Components'] = ' '.join(sorted([c.name for c in rss.suite.components]))

    meta_files_by_cs: dict[str, list[RepoFileInfo]] = {}
    for fi in sorted(meta_files):
        if fi.checksum_name not in meta_files_by_cs:
            meta_files_by_cs[fi.checksum_name] = []
        meta_files_by_cs[fi.checksum_name].append(fi)

    if only_sources:
        for cs_name in sorted(meta_files_by_cs.keys()):
            # patch in the updated sources data
            metafile_data = entry[cs_name].split('\n')
            for i, line in enumerate(metafile_data):
                for fi in meta_files_by_cs[cs_name]:
                    if line.endswith(fi.fname):
                        metafile_data[i] = f' {fi.checksum} {fi.size: >8} {fi.fname}'
            entry[cs_name] = '\n'.join(metafile_data)
    else:
        for cs_name in sorted(meta_files_by_cs.keys()):
            # add metadata
            metafile_data = [f' {f.checksum} {f.size: >8} {f.fname}' for f in meta_files_by_cs[cs_name]]
            entry[cs_name] = '\n' + '\n'.join(metafile_data)

    if os.path.islink(root_rel_fname):
        os.unlink(root_rel_fname)
    with open(root_rel_fname, 'w', encoding='utf-8') as f:
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
    if os.path.isdir(suite_repo_dist_dir):
        renameat2.exchange_paths(suite_temp_dist_dir, suite_repo_dist_dir)
        shutil.rmtree(suite_temp_dist_dir)
    else:
        os.rename(suite_temp_dist_dir, suite_repo_dist_dir)

    # all changes have been applied. This is a bit of a race-condition,
    # as some stuff may have been accepted while we are publishing data,
    # but this is usually something we can ignore on high-volume suites,
    # and we will also ensure that a suite gets published at least once
    # every week
    rss.changes_pending = False
    if only_sources:
        log.info('Published Sources index for suite: %s/%s', rss.repo.name, rss.suite.name)
        archive_log.info('PUBLISHED-SOURCES: %s/%s', rss.repo.name, rss.suite.name)
    else:
        log.info('Published suite: %s/%s', rss.repo.name, rss.suite.name)
        archive_log.info('PUBLISHED: %s/%s', rss.repo.name, rss.suite.name)


@concurrent.process(daemon=False, name='publish-repo-suite-dists', context=mproc.get_context('forkserver'))
def publish_suite_dists_async(
    repo_name: str,
    suite_name: str,
    *,
    dep11_src_dir: T.Optional[T.PathUnion],
    only_sources: bool = False,
    force: bool = False,
    lconf_fname: T.Optional[T.PathUnion] = None,
):
    """
    Parallel method for publishing data for a suite.
    :param repo_name: Name of the repository.
    :param suite_name: Name of the suite in the repository
    :param dep11_src_dir: Source directory for DEP-11 data
    :param force: Force publication
    :param only_sources: If True, update only the Sources index and ignore everything else.
    :param lconf_fname: Local configuration file to use in a subprocess, or None to use default.
    """
    from laniakea.logging import configure_pkg_archive_logger

    lconf = LocalConfig(lconf_fname)
    # reconfigure logging
    configure_pkg_archive_logger()

    with process_file_lock('publish_{}-{}'.format(repo_name, suite_name), wait=True):
        with session_scope() as session:
            rss = repo_suite_settings_for(session, repo_name, suite_name)
            _publish_suite_dists(
                lconf, session, rss, dep11_src_dir=dep11_src_dir, only_sources=only_sources, force=force
            )


def publish_repo_dists(
    session,
    repo: ArchiveRepository,
    *,
    suite_name: T.Optional[str] = None,
    only_sources: bool = False,
    force: bool = False,
):
    """
    Publish dists/ data for all (modified) suites in a repository.
    :param session: SQLAlchemy session
    :param repo: Repository to publish
    :param suite_name: Name of the suite to publish, or None to publish all.
    :param only_sources: If True, publish only the Sources index and ignore everything else.
    :return:
    """

    with process_file_lock('publish_{}'.format(repo.name), wait=True):
        # remove possible remnants of an older publish operation
        lconf = LocalConfig()
        temp_dists_dir = os.path.join(lconf.archive_root_dir, repo.name, 'zzz-meta')
        if os.path.isdir(temp_dists_dir):
            shutil.rmtree(temp_dists_dir)

        # import external data in parallel (we may be able to run more data import in parallel here in future,
        # at the moment we just have DEP-11)
        dep11_dir = None
        if not only_sources:
            dep11_future = _retrieve_dep11_data_async(repo.name, lconf.fname)
            success, error_msg, dep11_dir = dep11_future.result()  # pylint: disable=E1101
            if not success:
                raise Exception(error_msg)

        async_tasks = []
        for rss in repo.suite_settings:
            if suite_name:
                # skip any suites that we shouldn't process
                if rss.suite.name != suite_name:
                    continue
            future = publish_suite_dists_async(
                rss.repo.name,
                rss.suite.name,
                dep11_src_dir=dep11_dir,
                only_sources=only_sources,
                force=force,
                lconf_fname=lconf.fname,
            )
            async_tasks.append(future)

        # collect potential errors and wait for parallel tasks to complete
        for future in async_tasks:
            future.result()

        # ensure all temporary data is cleaned up
        if os.path.isdir(temp_dists_dir):
            shutil.rmtree(temp_dists_dir)
    log.info('Published repository: %s', repo.name)


@click.command()
@click.option(
    '--repo',
    'repo_name',
    default=None,
    help='Name of the repository to act on, if not set all repositories will be processed',
)
@click.option(
    '--suite',
    '-s',
    'suite_name',
    default=None,
    help='Name of the suite to act on, if not set all suites will be processed',
)
@click.option(
    '--only-sources',
    default=False,
    is_flag=True,
    help='Only update the Sources index and ignore all other metadata updates.',
)
@click.option(
    '--force',
    default=False,
    is_flag=True,
    help='Whether to force publication even if it is not yet needed.',
)
def publish(
    repo_name: T.Optional[str] = None,
    suite_name: T.Optional[str] = None,
    *,
    only_sources: bool = False,
    force: bool = False,
):
    """Publish repository metadata that clients can use."""

    with session_scope() as session:
        if repo_name:
            repo = session.query(ArchiveRepository).filter(ArchiveRepository.name == repo_name).one_or_none()
            if not repo:
                click.echo('Unable to find repository with name {}!'.format(repo_name), err=True)
                sys.exit(1)
            repos = [repo]
        else:
            repos = session.query(ArchiveRepository).all()

        for repo in repos:
            try:
                publish_repo_dists(session, repo, suite_name=suite_name, only_sources=only_sources, force=force)
            except Exception as e:
                console = Console()
                console.print_exception(max_frames=20)
                click.echo('Error while publishing repository {}: {}'.format(repo.name, str(e)), err=True)
                sys.exit(5)
