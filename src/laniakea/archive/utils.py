# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
# Copyright (C) 2018, Ansgar Burchardt <ansgar@debian.org>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import re

import apt_pkg
from sqlalchemy import and_, func

import laniakea.typing as T
from laniakea import LocalConfig
from laniakea.db import (
    DebType,
    ArchiveFile,
    PackageInfo,
    ArchiveSuite,
    DbgSymPolicy,
    SourcePackage,
    ArchiveSection,
    PackageOverride,
    PackagePriority,
    ArchiveComponent,
    ArchiveRepository,
    ArchiveQueueNewEntry,
    ArchiveRepoSuiteSettings,
)
from laniakea.utils import split_strip


class UploadError(Exception):
    """Issue while processing an upload"""

    pass


class ArchiveIntegrityError(Exception):
    """Something is wrong with the overall archive structure."""

    pass


orig_source_ext_re = r'orig(?:-[a-zA-Z0-9-]+)?\.tar\.(?:gz|bz2|xz)(?:\.asc)?'
file_source_ext_re = '(' + orig_source_ext_re + r'|(?:debian\.)?tar\.(?:gz|bz2|xz)|diff\.gz)'

# Prefix of binary and source filenames
_re_file_prefix = r'^(?P<package>[a-z0-9][a-z0-9.+-]+)_(?P<version>[A-Za-z0-9.~+-]+?)'

# Match upstream tarball
# Groups: package, version
re_file_orig = re.compile(_re_file_prefix + r'\.' + orig_source_ext_re)

# Match dsc files
# Groups: package, version
re_file_dsc = re.compile(_re_file_prefix + r'\.dsc$')

# Match other source files
# Groups: package, version
re_file_source = re.compile(_re_file_prefix + r'\.' + file_source_ext_re)

# Match buildinfo file
# Groups: package, version, suffix
re_file_buildinfo = re.compile(_re_file_prefix + r'_(?P<suffix>[a-zA-Z0-9+-]+)\.buildinfo$')

# Match binary packages
# Groups: package, version, architecture, type
re_file_binary = re.compile(_re_file_prefix + r'_(?P<architecture>[a-z0-9-]+)\.(?P<type>u?deb)$')


def checksums_list_to_file(cslist, checksum: str, files=None, *, base_dir=None) -> T.Dict[str, ArchiveFile]:
    """Convert a list of checkums (from a Sources, Packages or .dsc file) to ArchiveFile objects."""

    if not files:
        files = {}
    if not cslist:
        return files
    for fdata in cslist:
        basename = os.path.basename(fdata['name'])

        af = files.get(basename)
        if not af:
            if not base_dir:
                af = ArchiveFile(basename)
            else:
                af = ArchiveFile(os.path.join(base_dir, basename))

        if checksum == 'md5':
            af.md5sum = fdata['md5sum']
        else:
            setattr(af, checksum + 'sum', fdata[checksum])
        af.size = fdata['size']

        files[basename] = af

    return files


def parse_package_list_str(pkg_list_raw, default_version=None):
    '''
    Parse a "Package-List" field and return its information in
    PackageInfo data structures.
    See https://www.debian.org/doc/debian-policy/ch-controlfields.html#package-list
    '''

    res = []

    for line in pkg_list_raw.split('\n'):
        parts = split_strip(line, ' ')
        if len(parts) < 4:
            continue

        pi = PackageInfo()
        pi.name = parts[0]
        pi.version = default_version
        pi.deb_type = DebType.from_string(parts[1])
        pi.section = parts[2]
        if '/' in pi.section:
            pi.component, pi.section = pi.section.split('/', 2)
        pi.priority = PackagePriority.from_string(parts[3])

        if len(parts) > 4:
            # we have additional data
            raw_vals = split_strip(parts[4], ' ')
            for v in raw_vals:
                if v.startswith('arch='):
                    # handle architectures
                    pi.architectures = v[5:].split(',')

        res.append(pi)
    return res


def check_overrides_source(session, rss: ArchiveRepoSuiteSettings, spkg: SourcePackage) -> T.List[PackageInfo]:
    """Test if overrides for the binary package of a source packages are present.
    returns: List of packaging infos for missing overrides

    :param session: SQLAlchemy session
    :param rss: RepoSuiteSettings to check the override in
    :param spkg: Source package to check
    :return: List of missing overrides, or None
    """
    missing = []
    for bin in spkg.expected_binaries:
        res = (
            session.query(PackageOverride.id)
            .filter(PackageOverride.repo_suite_id == rss.id, PackageOverride.pkgname == bin.name)
            .first()
        )
        if res is not None:
            # override exists
            continue
        missing.append(bin)
    return missing


def repo_suite_settings_for(
    session, repo_name: str, suite_name: str, *, fail_if_missing: bool = True
) -> T.Optional[ArchiveRepoSuiteSettings]:
    """Obtain a RepoSuiteSettings instance."""
    rss_q = session.query(ArchiveRepoSuiteSettings).filter(
        ArchiveRepoSuiteSettings.repo.has(name=repo_name),
        ArchiveRepoSuiteSettings.suite.has(name=suite_name),
    )
    return rss_q.one() if fail_if_missing else rss_q.one_or_none()


def repo_suite_settings_for_debug(session, rss: ArchiveRepoSuiteSettings) -> T.Optional[ArchiveRepoSuiteSettings]:
    """Obtains the repo-suite-settings for the debug archive that corresponds to the given repo-suite-settings"""

    # add dbgsym to the same suite if no dedicated debug suite is set
    debug_suite_id = rss.suite.debug_suite_id
    debug_repo_id = rss.repo.debug_repo_id
    if not debug_suite_id:
        # return None for "no debugsymbs allowed at all"
        return None if rss.suite.dbgsym_policy == DbgSymPolicy.NO_DEBUG else rss
    if not debug_repo_id:
        debug_repo_id = rss.repo_id

    rss_dbg = (
        session.query(ArchiveRepoSuiteSettings)
        .filter(ArchiveRepoSuiteSettings.repo_id == debug_repo_id, ArchiveRepoSuiteSettings.suite_id == debug_suite_id)
        .one_or_none()
    )
    if not rss_dbg:
        dbg_repo = session.query(ArchiveRepository).filter(ArchiveRepository.id == debug_repo_id).one()
        raise ArchiveIntegrityError(
            'Unable to find configuration for debug suite location {}/{}'.format(
                dbg_repo.name, rss.suite.debug_suite.name
            )
        )
    return rss_dbg


def find_latest_source_package(session, rss: ArchiveRepoSuiteSettings, pkgname: str) -> T.Optional[SourcePackage]:
    """Find the most recent source package in a suite.

    :param session: SQLAlchemy session
    :param rss: Repo/suite to search in
    :param pkgname: Name of the package to look for
    :return: The source package, or None if none was found
    """

    spkg = (
        session.query(SourcePackage)
        .filter(
            SourcePackage.name == pkgname,
            SourcePackage.repo_id == rss.repo_id,
            SourcePackage.suites.any(id=rss.suite_id),
            SourcePackage.time_deleted.is_(None),
        )
        .order_by(SourcePackage.version.desc())
        .first()
    )
    return spkg


def register_package_overrides(session, rss: ArchiveRepoSuiteSettings, overrides: T.List[PackageInfo]):
    """Add selected overrides to the repository-suite combination they belong to.

    :param session: SQLAlchemy session
    :param rss: RepoSuiteSettings to add the overrides to.
    :param overrides: List of overrides to add.
    """

    rss_dbg = None
    for pi in overrides:
        real_rss = rss
        if pi.section == 'debug':
            # we have a debug package, which may live in a different repo/suite
            if not rss_dbg:
                rss_dbg = repo_suite_settings_for_debug(session, rss)
            if not rss_dbg:
                # don't add override if we will drop this dbgsym package anyway
                return
            real_rss = rss_dbg
        override = (
            session.query(PackageOverride)
            .filter(PackageOverride.repo_suite_id == real_rss.id, PackageOverride.pkgname == pi.name)
            .one_or_none()
        )
        if not override:
            override = PackageOverride(pi.name)
            override.repo_suite = real_rss
            override.pkgname = pi.name
            session.add(override)
        override.component = session.query(ArchiveComponent).filter(ArchiveComponent.name == pi.component).one()
        override.section = session.query(ArchiveSection).filter(ArchiveSection.name == pi.section).one_or_none()
        if not override.section:
            raise ValueError(
                'Archive section `{}` does not exist, even though `{}` thinks it does.'.format(pi.section, pi.name)
            )
        override.essential = pi.essential
        override.priority = pi.priority


def pool_dir_from_name_component(source_pkg_name: str, component_name: str):
    """Create a pool location string from a source package name"""
    if source_pkg_name[:3] == "lib":
        return os.path.join('pool', component_name, source_pkg_name[:4], source_pkg_name)
    else:
        return os.path.join('pool', component_name, source_pkg_name[:1], source_pkg_name)


def dists_dir_for_repo_suite(repo: ArchiveRepository, suite: ArchiveSuite):
    """Get dists/ directory for the given suite and repository."""
    return os.path.join(LocalConfig().archive_root_dir, repo.name, 'dists', suite.name)


def split_epoch(version: str):
    """Split epoch from a version string and return it separately"""
    parts = version.partition(':')
    if not parts[2]:
        # no epoch present
        return None, parts[0]
    else:
        # return epoch and version
        return parts[0], parts[2]


def upstream_version_with_epoch(version: str):
    """Extract the upstream package version, but keep the epoch."""
    if '-' not in version:
        return version
    return version.split('-', 1)[0]


def is_deb_file(fname: T.PathUnion):
    """Check if the file is a Debian binary package."""
    return str(fname).endswith(('.deb', '.udeb'))


def find_package_in_new_queue(session, rss: ArchiveRepoSuiteSettings, spkg: SourcePackage):
    """Find a source package in the NEW queue for a given repo-suite configuration."""
    nq_entry = (
        session.query(ArchiveQueueNewEntry)
        .filter(
            ArchiveQueueNewEntry.destination_id == rss.suite_id,
            ArchiveQueueNewEntry.package.has(name=spkg.name),
            ArchiveQueueNewEntry.package.has(version=spkg.version),
            ArchiveQueueNewEntry.package.has(repo_id=rss.repo_id),
        )
        .one_or_none()
    )
    return nq_entry


class AptVersion:
    def __init__(self, version):
        self.version = version

    def __str__(self):
        return str(self.version)

    def __eq__(self, other):
        return apt_pkg.version_compare(self.version, other.version) == 0

    def __lt__(self, other):
        return apt_pkg.version_compare(self.version, other.version) < 0

    def __le__(self, other):
        return apt_pkg.version_compare(self.version, other.version) <= 0

    def __gt__(self, other):
        return apt_pkg.version_compare(self.version, other.version) > 0

    def __ge__(self, other):
        return apt_pkg.version_compare(self.version, other.version) >= 0
