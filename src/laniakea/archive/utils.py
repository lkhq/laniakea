# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
# Copyright (C) 2018, Ansgar Burchardt <ansgar@debian.org>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import re
import shutil
import tempfile
import subprocess
from datetime import datetime
from contextlib import contextmanager

import apt_pkg
from apt_pkg import version_compare
from sqlalchemy import and_, select, bindparam

import laniakea.typing as T
from laniakea import LocalConfig
from laniakea.db import (
    DebType,
    ArchiveFile,
    PackageInfo,
    ArchiveSuite,
    DbgSymPolicy,
    BinaryPackage,
    SourcePackage,
    ArchiveSection,
    PackageOverride,
    PackagePriority,
    ArchiveComponent,
    ArchiveRepository,
    ArchiveArchitecture,
    ArchiveQueueNewEntry,
    ArchiveVersionMemory,
    ArchiveRepoSuiteSettings,
)
from laniakea.utils import run_command, split_strip, hardlink_or_copy
from laniakea.logging import log


class UploadError(Exception):
    """Issue while processing an upload"""


class ArchiveIntegrityError(Exception):
    """Something is wrong with the overall archive structure."""


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
    """Convert a list of checksums (from a Sources, Packages or .dsc file) to ArchiveFile objects."""

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


def parse_package_list(
    pkg_list_raw: str | list[dict[str, str]], default_version: str | None = None, default_archs: list[str] | None = None
):
    """
    Parse a "Package-List" field and return its information in
    PackageInfo data structures.
    See https://www.debian.org/doc/debian-policy/ch-controlfields.html#package-list
    """

    res = []
    if not default_archs:
        default_archs = []

    # Handle new python-debian format (list of dicts)
    if isinstance(pkg_list_raw, list):
        for entry in pkg_list_raw:
            pi = PackageInfo()
            pi.name = entry.get('package', '')
            pi.version = default_version
            pi.deb_type = DebType.from_string(entry.get('package-type', 'deb'))
            pi.section = entry.get('section', '')
            if '/' in pi.section:
                pi.component, pi.section = pi.section.split('/', 2)
            pi.priority = PackagePriority.from_string(entry.get('priority', 'optional'))

            # handle architectures from '_other' field or 'arch' field
            arch_str = entry.get('arch', '')
            if not arch_str:
                other = entry.get('_other', '')
                if other:
                    for part in other.split():
                        if part.startswith('arch='):
                            arch_str = part[5:]
                            break
            if arch_str:
                pi.architectures = arch_str.split(',')
            else:
                pi.architectures = default_archs
            res.append(pi)
        return res

    # Handle old string format
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
                    break

        if not pi.architectures:
            pi.architectures = default_archs
        res.append(pi)
    return res


def check_overrides_source(session, rss: ArchiveRepoSuiteSettings, spkg: SourcePackage) -> T.List[PackageInfo]:
    """Test if overrides for the binary packages of a source package are present.
    returns: List of packaging infos for missing overrides

    :param session: SQLAlchemy session
    :param rss: RepoSuiteSettings to check the override in
    :param spkg: Source package to check
    :return: List of missing overrides, or None
    """
    missing = []
    rss_dbg = repo_suite_settings_for_debug(session, rss)
    for bin in spkg.expected_binaries:
        if rss_dbg and bin.section == 'debug' and bin.name.endswith('-dbgsym'):
            res = (
                session.query(PackageOverride.id)
                .filter(
                    PackageOverride.repo_id == rss_dbg.repo_id,
                    PackageOverride.suite_id == rss_dbg.suite_id,
                    PackageOverride.pkg_name == bin.name,
                )
                .first()
            )
        else:
            res = (
                session.query(PackageOverride.id)
                .filter(
                    PackageOverride.repo_id == rss.repo_id,
                    PackageOverride.suite_id == rss.suite_id,
                    PackageOverride.pkg_name == bin.name,
                )
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


def package_mark_published(session, rss: ArchiveRepoSuiteSettings, pkg: T.Union[SourcePackage, BinaryPackage]):
    """
    Mark package as published.

    This updates the version memory and sets a publication date for the package..

    :param session: SQLAlchemy session
    :param rss: RepoSuite settings for this package
    :param pkg: Source or binary package.
    """

    arch_name = 'source' if isinstance(pkg, SourcePackage) else pkg.architecture.name
    vmem = (
        session.query(ArchiveVersionMemory)
        .filter(
            ArchiveVersionMemory.repo_suite_id == rss.id,
            ArchiveVersionMemory.pkg_name == pkg.name,
            ArchiveVersionMemory.arch_name == arch_name,
        )
        .one_or_none()
    )

    if vmem:
        # safety check, so we don't downgrade a version number accidentally (e.g. in case we were
        # ignoring previous version sanity checks)
        if version_compare(pkg.version, vmem.highest_version) > 0:
            vmem.highest_version = pkg.version
    else:
        vmem = ArchiveVersionMemory()
        vmem.repo_suite = rss
        vmem.pkg_name = pkg.name
        vmem.arch_name = arch_name
        vmem.highest_version = pkg.version  # type: ignore[assignment]
        session.add(vmem)

    # "undelete" package, just in case it is marked as deleted
    pkg.time_deleted = None

    # set publication time
    if not pkg.time_published:
        pkg.time_published = datetime.utcnow()


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


def register_package_overrides(
    session, rss: ArchiveRepoSuiteSettings, overrides: T.List[PackageInfo], *, allow_invalid_section=False
):
    """Add selected overrides to the repository-suite combination they belong to.

    :param session: SQLAlchemy session
    :param rss: RepoSuiteSettings to add the overrides to.
    :param overrides: List of overrides to add.
    :param allow_invalid_section: Allow invalid overrides (will be converted to "misc")
    """

    rss_dbg = None
    for pi in overrides:
        real_rss = rss
        if pi.section == 'debug' and pi.name.endswith('-dbgsym'):
            # we have a debug package, which may live in a different repo/suite
            if not rss_dbg:
                rss_dbg = repo_suite_settings_for_debug(session, rss)
            if not rss_dbg:
                # don't add override if we will drop this dbgsym package anyway
                return
            real_rss = rss_dbg
        override = (
            session.query(PackageOverride)
            .filter(
                PackageOverride.repo_id == real_rss.repo_id,
                PackageOverride.suite_id == real_rss.suite_id,
                PackageOverride.pkg_name == pi.name,
            )
            .one_or_none()
        )
        override_new = False
        if not override:
            override = PackageOverride(pi.name, real_rss.repo, real_rss.suite)
            override_new = True

        component = session.query(ArchiveComponent).filter(ArchiveComponent.name == pi.component).one_or_none()
        if not component:
            log.warning(
                'Skipping registering override for "%s" in "%s", as its component "%s" is not known.',
                pi.name,
                real_rss.repo.name,
                pi.component,
            )
            continue
        override.component = component

        override.section = session.query(ArchiveSection).filter(ArchiveSection.name == pi.section).one_or_none()
        if not override.section:
            if allow_invalid_section:
                # we just throw a package with a bad section into "misc"
                override.section = session.query(ArchiveSection).filter(ArchiveSection.name == 'misc').one_or_none()
            else:
                raise ValueError(
                    'Archive section `{}` does not exist, even though `{}` thinks it does.'.format(pi.section, pi.name)
                )
        override.essential = pi.essential
        override.priority = pi.priority

        if override_new:
            session.add(override)


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


binary_select_query = select(BinaryPackage).where(
    and_(
        BinaryPackage.repo_id == bindparam('repo_id'),
        BinaryPackage.suites.any(id=bindparam('suite_id')),
        BinaryPackage.source_id == bindparam('source_id'),
        BinaryPackage.architecture_id == bindparam('arch_id'),
    )
)


def binaries_exist_for_package(session, rss: ArchiveRepoSuiteSettings, spkg: SourcePackage, arch: ArchiveArchitecture):
    '''
    Get list of binary packages built for the given source package.
    '''

    return (
        session.query(binary_select_query.exists())
        .params(
            repo_id=rss.repo.id,
            suite_id=rss.suite.id,
            source_id=spkg.uuid,
            arch_id=arch.id,
        )
        .scalar()
    )


re_parse_lintian = re.compile(r"^(?P<level>W|E|O|I|P): (?P<package>.*?): (?P<tag>[^ ]*) ?(?P<description>.*)$")


def lintian_check(fname: T.PathUnion, *, tags: list[str] = None) -> tuple[bool, list[dict[str, str]]]:
    """
    Run Lintian check in a Bubblewrap container on a selected package.
    :param fname: Name of the file to check
    :param tags: Tags to verify.
    :return: A tuple, containing the success as bool and the resulting tags.
    """

    with tempfile.TemporaryDirectory(prefix='lk-lintian-bwrap_') as tmp_dir:
        ro_bind = ['/lib', '/bin', '/usr', '/etc/dpkg', '/var/tmp']
        if os.path.isdir('/lib64'):
            ro_bind.append('/lib64')
        command = ['bwrap']
        for loc in ro_bind:
            command.extend(['--ro-bind', loc, loc])
        command.extend(
            [
                '--bind',
                '/tmp',
                tmp_dir,
                '--bind',
                os.path.dirname(fname),
                '/srv/ws',
                '--unshare-pid',
                '--unshare-net',
                '--unshare-user',
                '--unshare-ipc',
                '--proc',
                '/proc',
                '--bind',
                '/dev/urandom',
                '/dev/random',
                '--',
            ]
        )

        command.extend(['lintian', '-IE', '--pedantic'])
        if tags:
            command.extend(['--tags', ','.join(tags)])
        command.append(os.path.join('/srv/ws', os.path.basename(fname)))

        # run lintian
        out, err, ret = run_command(command)

        result_tags = []
        if out:
            for line in out.splitlines():
                m = re_parse_lintian.match(line)
                if m:
                    result_tags.append(m.groupdict())

        if ret == 1 and not result_tags:
            raise RuntimeError('Failed to run Lintain (Code: {}, Error: {}{})'.format(ret, err, out))

        if not out and ret != 0:
            # create a fake error with the crash information
            result_tags.append(
                {'level': 'E', 'package': '_internal', 'tag': 'x-internal-issue-running-lintian', 'error': err}
            )

        # ret will be 2 in case there was any error
        return (ret == 0, result_tags)


class UnpackedSource:
    """
    Extract source package and provide methods for accessing its contents.
    """

    def __init__(self, dsc_fname: T.PathUnion, lconf: LocalConfig | None = None):
        """
        :param dsc_fname: The file to extract.
        :param lconf: LocalConfig to use
        """
        self._root_directory = None
        if not lconf:
            lconf = LocalConfig()

        tmp_dir = tempfile.mkdtemp(dir=lconf.cache_dir, prefix='usrc_')
        self._root_directory = os.path.join(tmp_dir, 'root')
        command = ('dpkg-source', '--no-copy', '--no-check', '-q', '-x', dsc_fname, self._root_directory)
        subprocess.check_call(command)

    @property
    def root_directory(self):
        """Directory where debian/ subdir is located."""
        return self._root_directory

    def cleanup(self):
        """Delete temporary files."""
        if self._root_directory is None:
            return
        parent_directory = os.path.dirname(self.root_directory)
        shutil.rmtree(parent_directory)
        self._root_directory = None

    def __del__(self):
        self.cleanup()


@contextmanager
def unpack_source(dsc_fname: T.PathUnion, lconf: LocalConfig | None = None) -> T.Iterator[UnpackedSource]:
    """Unpack source file to a temporary directory to investigate its contents."""

    srcdir = UnpackedSource(dsc_fname, lconf)
    try:
        yield srcdir
    finally:
        srcdir.cleanup()


def publish_package_metadata(spkg: SourcePackage, lconf: LocalConfig | None = None):
    """Extract changelog/copyright and put it to the right location for the given source package."""

    if not lconf:
        lconf = LocalConfig()

    # check if we even need to do anything
    pm_dir = spkg.get_metadata_dir(lconf)
    spkg_basename = '{}_{}'.format(spkg.name, split_epoch(spkg.version)[1])

    spkg_changelog_fname = os.path.join(pm_dir, spkg_basename + '_changelog')
    spkg_copyright_fname = os.path.join(pm_dir, spkg_basename + '_copyright')
    if not os.path.isfile(spkg_changelog_fname) or not os.path.isfile(spkg_copyright_fname):
        # some files are missing, extract them from the source!
        log.info('Extracting auxiliary package metadata for "%s"', str(spkg))
        os.makedirs(pm_dir, exist_ok=True)
        dsc_f = spkg.dsc_file
        with unpack_source(dsc_f.absolute_repo_path, lconf) as usrc:
            changelog_fname = os.path.join(usrc.root_directory, 'debian', 'changelog')
            copyright_fname = os.path.join(usrc.root_directory, 'debian', 'copyright')
            if os.path.isfile(changelog_fname):
                shutil.copy(changelog_fname, spkg_changelog_fname)
            else:
                log.error(
                    'Source package "%s" is missing its debian/changelog file! This should never happen.', str(spkg)
                )
            if os.path.isfile(copyright_fname):
                shutil.copy(copyright_fname, spkg_copyright_fname)
            else:
                log.warning('Source package "%s" is missing a debian/copyright file!', str(spkg))

    # update alias hardlinks
    have_changelog = os.path.isfile(spkg_changelog_fname)
    have_copyright = os.path.isfile(spkg_copyright_fname)
    for suite in spkg.suites:
        if have_changelog:
            hardlink_or_copy(spkg_changelog_fname, os.path.join(pm_dir, suite.name + '_changelog'), override=True)
        if have_copyright:
            hardlink_or_copy(spkg_copyright_fname, os.path.join(pm_dir, suite.name + '_copyright'), override=True)
