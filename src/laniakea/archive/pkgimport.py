# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import shutil
import hashlib
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
from collections import namedtuple
from dataclasses import dataclass

from apt_pkg import Hashes
from sqlalchemy import exists
from debian.deb822 import Sources, Packages

import laniakea.typing as T
from laniakea import LkModule
from laniakea.db import (
    DebType,
    NewPolicy,
    ArchiveFile,
    PackageInfo,
    BinaryPackage,
    SourcePackage,
    ArchiveSection,
    ChangesUrgency,
    ArchiveUploader,
    PackageOverride,
    PackagePriority,
    ArchiveComponent,
    ArchiveRepository,
    ArchiveArchitecture,
    ArchiveQueueNewEntry,
    ArchiveVersionMemory,
    ArchiveRepoSuiteSettings,
)
from laniakea.utils import safe_strip, safe_rename, split_strip, hardlink_or_copy
from laniakea.logging import log, archive_log
from laniakea.msgstream import EventEmitter
from laniakea.localconfig import LocalConfig, LintianConfig
from laniakea.archive.utils import (
    UploadError,
    is_deb_file,
    split_epoch,
    re_file_orig,
    lintian_check,
    check_overrides_source,
    checksums_list_to_file,
    package_mark_published,
    parse_package_list_str,
    register_package_overrides,
    pool_dir_from_name_component,
    repo_suite_settings_for_debug,
)
from laniakea.archive.changes import (
    Changes,
    ChangesFileEntry,
    InvalidChangesError,
    parse_changes,
)


class ArchiveImportError(Exception):
    """Import of a package into the archive failed."""


class ArchiveImportNewError(ArchiveImportError):
    """Import of a package into the archive ended in a queue unexpectedly."""


class ArchivePackageExistsError(ArchiveImportError):
    """Import of a package into the archive failed because it already existed."""


class HashVerifyError(Exception):
    """Hash verification failed."""


def pop_split(d, key, s):
    """Pop value from dict :d with key :key and split with :s"""
    value = d.pop(key, None)
    if not value:
        return []
    return split_strip(value, s)


def verify_hashes(file: T.Union[ChangesFileEntry, ArchiveFile], local_fname: T.Union[os.PathLike, str]):
    """Verifies all known hashes of :file"""
    hashes_checked = 0
    with open(local_fname, 'rb') as f:
        # pylint: disable=not-an-iterable
        for hash in Hashes(f).hashes:  # type: ignore
            if hash.hashtype == 'MD5Sum':
                hash_okay = file.md5sum == hash.hashvalue
            elif hash.hashtype == 'SHA1':
                hash_okay = file.sha1sum == hash.hashvalue
            elif hash.hashtype == 'SHA256':
                hash_okay = file.sha256sum == hash.hashvalue
            elif hash.hashtype == 'SHA512':
                if file.sha512sum is not None:
                    hash_okay = file.sha512sum == hash.hashvalue
            elif hash.hashtype == 'Checksum-FileSize':
                hash_okay = int(file.size) == int(hash.hashvalue)
            else:
                raise HashVerifyError(
                    'Unknown hash type "{}" - Laniakea likely needs to be adjusted to a new APT version.'.format(
                        hash.hashtype
                    )
                )
            if not hash_okay:
                raise HashVerifyError(
                    '{} checksum validation of "{}" failed (expected {}).'.format(
                        hash.hashtype, file.fname, hash.hashvalue
                    )
                )
            hashes_checked += 1
    if hashes_checked < 4:
        raise HashVerifyError('An insufficient amount of hashes was validated for "{}" - this is a bug.')


# result tuple of import_source
ImportSourceResult = namedtuple('ImportSourceResult', 'pkg is_new')


class PackageImporter:
    """
    Imports packages into the archive directly,
    without performing any policy/permission checks.
    """

    def __init__(self, session, repo_suite_settings: ArchiveRepoSuiteSettings):
        self._session = session
        self._rss = repo_suite_settings

        self._repo_root = self._rss.repo.get_root_dir()
        self._repo_newqueue_root = self._rss.repo.get_new_queue_dir()
        os.makedirs(self._repo_newqueue_root, exist_ok=True)

        self._keep_source_packages = False
        self._prefer_hardlinks = False
        self._ensure_not_frozen()

    @property
    def current_session(self):
        return self._session

    @property
    def repo_suite_settings(self) -> ArchiveRepoSuiteSettings:
        return self._rss

    @property
    def keep_source_packages(self) -> bool:
        """True if source packages should be moved after import, otherwise they are kept in their original location."""
        return self._keep_source_packages

    @keep_source_packages.setter
    def keep_source_packages(self, v: bool):
        self._keep_source_packages = v

    @property
    def prefer_hardlinks(self) -> bool:
        """If True, we will make an attempt to use hardlinks instead of copies if possible, when copying packages."""
        return self._prefer_hardlinks

    @prefer_hardlinks.setter
    def prefer_hardlinks(self, v: bool):
        self._prefer_hardlinks = v

    def _ensure_not_frozen(self):
        if self._rss.frozen:
            raise ArchiveImportError(
                'Can not import anything into frozen repo/suite `{}/{}`.'.format(
                    self._rss.repo.name, self._rss.suite.name
                )
            )

    def _copy_or_move(self, src, dst, *, override: bool = False):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if override:
            if os.path.isfile(dst):
                os.unlink(dst)
        if self.keep_source_packages:
            if self._prefer_hardlinks:
                hardlink_or_copy(src, dst)
            else:
                shutil.copy(src, dst)
            shutil.chown(dst, user=os.getuid(), group=os.getgid())
            os.chmod(dst, 0o755)
            log.debug('Copied package file: %s -> %s', src, dst)
        else:
            safe_rename(src, dst)
            log.debug('Moved package file: %s -> %s', src, dst)

    def import_source(
        self,
        dsc_fname: T.Union[os.PathLike, str],
        component_name: str,
        *,
        new_policy: NewPolicy = NewPolicy.DEFAULT,
        error_if_new: bool = False,
        ignore_existing: bool = False,
        ignore_version_check: bool = False,
        ignore_bad_section: bool = False,
    ) -> ImportSourceResult:
        """Import a source package into the given suite or its NEW queue.

        :param dsc_fname: Path to a source package to import
        :param component_name: Name of the archive component to import into.
        :param skip_new: True if the NEW queue should be skipped and overrides be added automatically.
        """
        self._ensure_not_frozen()

        log.info('Attempting import of source: %s', dsc_fname)
        dsc_dir = os.path.dirname(dsc_fname)

        aftp_env = {'LANG': 'C.UTF-8', 'PATH': os.environ['PATH']}
        p = subprocess.run(
            ['apt-ftparchive', '-q', 'sources', dsc_fname],
            capture_output=True,
            check=True,
            encoding='utf-8',
            env=aftp_env,
        )
        if p.returncode != 0:
            raise ArchiveImportError('Failed to extract source package information: {}'.format(p.stderr))
        src_tf = Sources(p.stdout)
        if 'Package' not in src_tf:
            raise ArchiveImportError('Unable to gather valid source package information: {}'.format(p.stderr))

        pkgname = safe_strip(src_tf.pop('Package'))
        version = safe_strip(src_tf.pop('Version'))

        result = (
            self._session.query(ArchiveVersionMemory.highest_version)
            .filter(
                ArchiveVersionMemory.repo_suite_id == self._rss.id,
                ArchiveVersionMemory.arch_name == 'source',
                ArchiveVersionMemory.pkg_name == pkgname,
                ArchiveVersionMemory.highest_version > version,
            )
            .one_or_none()
        )
        if result:
            if ignore_existing:
                return ImportSourceResult(None, False)
            if not ignore_version_check:
                raise ArchiveImportError(
                    (
                        'Unable to import package "{}": '
                        'We have already seen higher version "{}" in {}:{} before.\n'
                        'Uploads must have a higher version than already present in the archive.'
                    ).format(pkgname, result[0], self._rss.repo.name, self._rss.suite.name)
                )

        if not component_name:
            raise ArchiveImportError('Unable to import source package without explicit component name.')

        spkg = SourcePackage(pkgname, version, self._rss.repo)
        spkg.component = self._session.query(ArchiveComponent).filter(ArchiveComponent.name == component_name).one()

        # check if this package is currently in the NEW queue, and if it is just update it
        nq_entry = (
            self._session.query(ArchiveQueueNewEntry)
            .filter(
                ArchiveQueueNewEntry.destination_id == self._rss.suite_id,
                ArchiveQueueNewEntry.package.has(name=spkg.name),
                ArchiveQueueNewEntry.package.has(version=spkg.version),
                ArchiveQueueNewEntry.package.has(repo_id=self._rss.repo_id),
            )
            .one_or_none()
        )
        if nq_entry:
            spkg = nq_entry.package
        else:
            # check if the package already exists
            ret = self._session.query(
                exists().where(
                    SourcePackage.repo_id == self._rss.repo_id,
                    SourcePackage.name == pkgname,
                    SourcePackage.version == version,
                )
            ).scalar()
            if ret:
                if ignore_existing:
                    return ImportSourceResult(None, False)
                raise ArchivePackageExistsError(
                    'Can not import source package {}/{}: Already exists.'.format(pkgname, version)
                )
            spkg.time_added = datetime.utcnow()

        spkg.format_version = safe_strip(src_tf.pop('Format'))
        spkg.standards_version = safe_strip(src_tf.pop('Standards-Version', None))
        spkg.architectures = pop_split(src_tf, 'Architecture', ' ')
        spkg.maintainer = safe_strip(src_tf.pop('Maintainer'))
        spkg.original_maintainer = safe_strip(src_tf.pop('Original-Maintainer', None))
        spkg.uploaders = pop_split(src_tf, 'Uploaders', ',')
        spkg.homepage = safe_strip(src_tf.pop('Homepage', None))
        spkg.vcs_browser = safe_strip(src_tf.pop('Vcs-Browser', None))
        spkg.vcs_git = safe_strip(src_tf.pop('Vcs-Git', None))

        spkg_dsc_text = safe_strip(src_tf.pop('Description', None))
        if spkg_dsc_text:
            # some source packages actually have a description text
            spkg.description = spkg_dsc_text
            spkg.summary = spkg_dsc_text.split('\n', 1)[0].strip()

        spkg.testsuite = pop_split(src_tf, 'Testsuite', ',')
        spkg.testsuite_triggers = pop_split(src_tf, 'Testsuite-Triggers', ',')

        spkg.build_depends = pop_split(src_tf, 'Build-Depends', ',')
        spkg.build_depends_indep = pop_split(src_tf, 'Build-Depends-Indep', ',')
        spkg.build_depends_arch = pop_split(src_tf, 'Build-Depends-Arch', ',')
        spkg.build_conflicts = pop_split(src_tf, 'Build-Conflicts', ',')
        spkg.build_conflicts_indep = pop_split(src_tf, 'Build-Conflicts-Indep', ',')
        spkg.build_conflicts_arch = pop_split(src_tf, 'Build-Conflicts-Arch', ',')
        if 'Package-List' in src_tf:
            spkg.expected_binaries = parse_package_list_str(src_tf.pop('Package-List'))
            src_tf.pop('Binary')
        else:
            log.warning(
                'Source package dsc file `{}/{}` had no `Package-List` '
                '- falling back to parsing `Binaries`.'.format(pkgname, version)
            )
            binary_stubs = []
            for b in pop_split(src_tf, 'Binary', ','):
                pi = PackageInfo()
                pi.name = b
                pi.component = spkg.component.name
                binary_stubs.append(pi)
            spkg.expected_binaries = binary_stubs

        # set package section, guess it if necessary
        section_name = safe_strip(src_tf.pop('Section', None))
        if not section_name and len(spkg.expected_binaries) >= 1:
            # take section name from the first binary entry
            section_name = spkg.expected_binaries[0].section
            if not section_name:
                # fall back to "misc"
                log.warning(
                    'Unable to determine section name for new source `%s/%s` targeted at %s/%s. Assuming `misc`.',
                    spkg.name,
                    spkg.version,
                    self._rss.repo.name,
                    self._rss.suite.name,
                )
                section_name = 'misc'
        spkg.section = self._session.query(ArchiveSection).filter(ArchiveSection.name == section_name).one_or_none()
        if not spkg.section:
            if ignore_bad_section:
                log.warning('Ignoring bad section "%s" for %s/%s', section_name, pkgname, version)
                spkg.section = self._session.query(ArchiveSection).filter(ArchiveSection.name == 'misc').one()
            else:
                raise ArchiveImportError('Section {} for {}/{} does not exist.'.format(section_name, pkgname, version))

        spkg.directory = pool_dir_from_name_component(pkgname, spkg.component.name)
        files = checksums_list_to_file(src_tf.pop('Files'), 'md5')
        files = checksums_list_to_file(src_tf.pop('Checksums-Sha1'), 'sha1', files)
        files = checksums_list_to_file(src_tf.pop('Checksums-Sha256'), 'sha256', files)
        files = checksums_list_to_file(src_tf.pop('Checksums-Sha512', None), 'sha512', files)

        missing_overrides = check_overrides_source(self._session, self._rss, spkg)
        if new_policy == NewPolicy.NEVER_NEW:
            is_new = False
        elif new_policy == NewPolicy.ALWAYS_NEW:
            is_new = True
        else:
            is_new = len(missing_overrides) != 0
        was_new = True if nq_entry and not is_new else False

        # remove any old file entries, in case we are updating
        # a package that is placed in NEW
        if nq_entry and spkg.files:
            for file in spkg.files:
                other_owner = (
                    self._session.query(SourcePackage.uuid)
                    .filter(SourcePackage.files.any(id=file.id), SourcePackage.uuid != spkg.uuid)
                    .first()
                )
                if not other_owner:
                    self._session.delete(file)
            spkg.files.clear()
            self._session.flush()

        files_todo = []
        for new_file in files.values():
            # ensure the files hashes are correct
            verify_hashes(new_file, os.path.join(dsc_dir, new_file.fname))

            pool_fname = os.path.join(spkg.directory, new_file.fname)
            self._session.flush()
            afile = (
                self._session.query(ArchiveFile)
                .filter(
                    ArchiveFile.repo_id == self._rss.repo_id,
                    ArchiveFile.fname == pool_fname,
                )
                .one_or_none()
            )
            if afile:
                # we have an existing registered file!
                if afile.sha1sum != new_file.sha1sum:
                    raise ArchiveImportError(
                        'File {} does not match SHA1 checksum of file in archive: {} != {}'.format(
                            new_file.fname, new_file.sha1sum, afile.sha1sum
                        )
                    )
                if afile.sha256sum != new_file.sha256sum:
                    raise ArchiveImportError(
                        'File {} does not match SHA256 checksum of file in archive: {} != {}'.format(
                            new_file.fname, new_file.sha256sum, afile.sha256sum
                        )
                    )
                if afile.sha512sum != new_file.sha512sum:
                    raise ArchiveImportError(
                        'File {} does not match SHA256 checksum of file in archive: {} != {}'.format(
                            new_file.fname, new_file.sha512sum, afile.sha512sum
                        )
                    )

                if is_new:
                    # file will be in NEW or is moving out of NEW, so we always need to copy/move it,
                    # unless it is a preexisting orig.tar.* file (possibly registered to another
                    #  source package version), in which case we will skip it
                    files_todo.append(afile)
                elif was_new and not re_file_orig.match(os.path.basename(afile.fname)):
                    files_todo.append(afile)
            else:
                # we have a new file!
                afile = new_file
                afile.repo = self._rss.repo
                afile.fname = pool_fname
                files_todo.append(afile)
                self._session.add(afile)

            spkg.files.append(afile)

        if missing_overrides and new_policy == NewPolicy.NEVER_NEW:
            # if we are supposed to skip NEW, we just register the overrides and add the package
            # to its designated suite
            register_package_overrides(self._session, self._rss, missing_overrides)
            spkg.suites.append(self._rss.suite)
        else:
            if missing_overrides or new_policy == NewPolicy.ALWAYS_NEW:
                # add to NEW queue (update entry or create new one)
                if not nq_entry:
                    nq_entry = ArchiveQueueNewEntry(spkg, self._rss.suite)
                    self._session.add(nq_entry)

                nq_entry.package = spkg
                nq_entry.destination = self._rss.suite
                if error_if_new:
                    raise ArchiveImportNewError('Package `{}/{}` is NEW'.format(pkgname, version))
            else:
                # no missing overrides, the package is good to go
                spkg.suites.append(self._rss.suite)

        if is_new:
            # we just delete the existing queue directory contents
            # FIXME: This means the last-processed upload "wins", while it should
            # actually be the latest upload that gets moved into the cache and processed
            # We will need to do some sorting in advance here to avoid this condition
            old_newq_dir = os.path.join(self._repo_newqueue_root, spkg.directory)
            if os.path.isdir(old_newq_dir):
                log.debug('Removing old package contents from NEW queue: %s', old_newq_dir)
                shutil.rmtree(old_newq_dir)

        for file in files_todo:
            if is_new:
                # move package to the NEW queue
                pool_fname_full = os.path.join(self._repo_newqueue_root, file.fname)
            else:
                # move package to the archive pool
                pool_fname_full = os.path.join(self._repo_root, file.fname)

            if not is_new and os.path.exists(pool_fname_full):
                raise ArchiveImportError(
                    'Destination source file `{}` already exists. Can not continue'.format(file.fname)
                )
            self._copy_or_move(os.path.join(dsc_dir, os.path.basename(file.fname)), pool_fname_full, override=is_new)
            self._session.add(file)

        if not is_new and nq_entry:
            # the package is no longer NEW (all overrides are added), but apparently
            # we have a NEW queue entry - get rid of that
            self._session.delete(nq_entry)

        # drop directory key, we don't need it
        src_tf.pop('Directory')

        # store any remaining fields as extra data
        extra_data = dict(src_tf)
        if extra_data:
            log.debug('Extra data fields for `{}/{}`: {}'.format(pkgname, version, dict(src_tf)))
            spkg.extra_data = dict(src_tf)

        self._session.add(spkg)
        if is_new:
            log.info(
                'Source `{}/{}` for {}/{} added to NEW queue.'.format(
                    spkg.name, spkg.version, self._rss.repo.name, self._rss.suite.name
                )
            )
        else:
            package_mark_published(self._session, self._rss, spkg)
            self._rss.changes_pending = True
            log.info(
                'Added source `{}/{}` to {}/{}.'.format(
                    spkg.name, spkg.version, self._rss.repo.name, self._rss.suite.name
                )
            )
            self._session.commit()
        return ImportSourceResult(spkg, is_new)

    def _find_source_package(
        self, deb_rss: ArchiveRepoSuiteSettings, source_name: str, source_version: str
    ) -> T.Tuple[T.Optional[SourcePackage], bool]:
        """Find the respective binary package.

        This function will find a source package, no matter if it is in a NEW queue, in the same
        repository as the binary package (e.g. a debug repository) or in the current target.
        """

        source = (
            self._session.query(SourcePackage)
            .filter(
                SourcePackage.repo_id == deb_rss.repo_id,
                SourcePackage.suites.any(id=deb_rss.suite_id),
                SourcePackage.name == source_name,
                SourcePackage.version == source_version,
            )
            .one_or_none()
        )
        if source:
            return source, False

        if deb_rss.id != self._rss.id:
            # maybe the package is in the non-debug suite?
            source = (
                self._session.query(SourcePackage)
                .filter(
                    SourcePackage.repo_id == self._rss.repo_id,
                    SourcePackage.suites.any(id=self._rss.suite_id),
                    SourcePackage.name == source_name,
                    SourcePackage.version == source_version,
                )
                .one_or_none()
            )
            if source:
                return source, False

        # maybe the package is in NEW?
        nq_entry = (
            self._session.query(ArchiveQueueNewEntry)
            .join(ArchiveQueueNewEntry.package)
            .filter(
                SourcePackage.repo_id == deb_rss.repo_id,
                ArchiveQueueNewEntry.destination_id == deb_rss.suite_id,
                SourcePackage.name == source_name,
                SourcePackage.version == source_version,
            )
            .one_or_none()
        )
        if nq_entry:
            return nq_entry.package, True

        nq_entry = (
            self._session.query(ArchiveQueueNewEntry)
            .join(ArchiveQueueNewEntry.package)
            .filter(
                SourcePackage.repo_id == self._rss.repo_id,
                ArchiveQueueNewEntry.destination_id == self._rss.suite_id,
                SourcePackage.name == source_name,
                SourcePackage.version == source_version,
            )
            .one_or_none()
        )
        if nq_entry:
            return nq_entry.package, True

        # we found nothing
        return None, False

    def import_binary(
        self,
        deb_fname: T.Union[os.PathLike, str],
        component_name: T.Optional[str] = None,
        *,
        ignore_existing: bool = False,
        ignore_version_check: bool = False,
        override_section: T.Optional[str] = None,
        ignore_missing_override: bool = False,
    ) -> BinaryPackage | None:
        """Import a binary package into the given suite or its NEW queue.

        :param deb_fname: Path to a deb/udeb package to import
        :param component_name: Name of the archive component to import into.
        :param ignore_existing: Ignore any already existing binary
        :param ignore_version_check: Ignore version check (import older versions / ones seen before)
        :param override_section: Set a new target section name, overriding the package selection.
        :param ignore_missing_override: Try to guess & add an override for this binary in case it is missing.
        """
        self._ensure_not_frozen()

        log.debug('Attempting import of binary: %s', deb_fname)
        pkg_type = DebType.DEB
        if os.path.splitext(deb_fname)[1] == '.udeb':
            pkg_type = DebType.UDEB

        aftp_env = {'LANG': 'C.UTF-8', 'PATH': os.environ['PATH']}
        p = subprocess.run(
            ['apt-ftparchive', '-q', 'packages', deb_fname],
            capture_output=True,
            check=True,
            encoding='utf-8',
            env=aftp_env,
        )
        bin_tf = Packages(p.stdout)
        if 'Package' not in bin_tf:
            raise ArchiveImportError('Unable to gather valid binary package information: {}'.format(p.stderr))

        p = subprocess.run(
            ['apt-ftparchive', '-q', 'contents', deb_fname],
            capture_output=True,
            check=True,
            encoding='utf-8',
            env=aftp_env,
        )
        filelist_raw = p.stdout.splitlines()

        pkgname = safe_strip(bin_tf.pop('Package'))
        version = safe_strip(bin_tf.pop('Version'))
        pkgarch = safe_strip(bin_tf.pop('Architecture'))

        deb_rss = self._rss
        deb_component = 'main'
        section = override_section if override_section else bin_tf.get('Section')
        if '/' in section:
            deb_component, section = section.split('/')
        is_debug_pkg = True if section == 'debug' and pkgname.endswith('-dbgsym') else False
        if is_debug_pkg:
            deb_rss = repo_suite_settings_for_debug(self._session, self._rss)
            if not deb_rss:
                log.info(
                    'Skipped import of `{}`: Not allowed or no debug-symbol location.'.format(
                        os.path.basename(deb_fname)
                    )
                )
                return None
        if not component_name:
            component_name = deb_component

        # check if the package already exists
        ret = self._session.query(
            exists().where(
                BinaryPackage.repo_id == deb_rss.repo_id,
                BinaryPackage.name == pkgname,
                BinaryPackage.version == version,
                BinaryPackage.architecture.has(name=pkgarch),
            )
        ).scalar()
        if ret:
            if ignore_existing:
                return None
            raise ArchivePackageExistsError(
                'Can not import binary package {}/{}/{}: Already exists.'.format(pkgname, version, pkgarch)
            )

        # ensure we are not downgrading binary package versions
        high_ver_res = (
            self._session.query(ArchiveVersionMemory.highest_version)
            .filter(
                ArchiveVersionMemory.repo_suite_id == self._rss.id,
                ArchiveVersionMemory.pkg_name == pkgname,
                ArchiveVersionMemory.arch_name == pkgarch,
                ArchiveVersionMemory.highest_version > version,
            )
            .one_or_none()
        )
        if high_ver_res:
            if not ignore_version_check:
                raise ArchiveImportError(
                    'Unable to import binary package "{}": '
                    'We have already seen higher version "{}" in this repository/suite before.'.format(
                        pkgname, high_ver_res[0]
                    )
                )

        bpkg = BinaryPackage(pkgname, version, deb_rss.repo)

        bpkg.architecture = self._session.query(ArchiveArchitecture).filter(ArchiveArchitecture.name == pkgarch).one()
        bpkg.update_uuid()

        bpkg.deb_type = pkg_type
        bpkg.maintainer = safe_strip(bin_tf.pop('Maintainer'))
        bpkg.original_maintainer = safe_strip(bin_tf.pop('Original-Maintainer', None))
        bpkg.homepage = safe_strip(bin_tf.pop('Homepage', None))
        bpkg.size_installed = int(bin_tf.pop('Installed-Size', '0'))
        bpkg.time_added = datetime.utcnow()

        source_info_raw = bin_tf.pop('Source', '')
        if not source_info_raw:
            source_name = pkgname
            source_version = version
        elif '(' in source_info_raw:
            source_name = source_info_raw[0 : source_info_raw.index('(') - 1].strip()
            source_version = source_info_raw[source_info_raw.index('(') + 1 : source_info_raw.index(')')].strip()
        else:
            source_name = source_info_raw
            source_version = version

        # find the corresponding source package
        bpkg.source, is_new = self._find_source_package(deb_rss, source_name, source_version)
        if not bpkg.source:
            if deb_rss.id == self._rss.id:
                search_msg = 'looked for {}/{} in {}:{}'.format(
                    source_name, source_version, deb_rss.repo.name, deb_rss.suite.name
                )
            else:
                search_msg = 'looked for {}/{} in {}:{} and {}:{}'.format(
                    source_name,
                    source_version,
                    deb_rss.repo.name,
                    deb_rss.suite.name,
                    self._rss.repo.name,
                    self._rss.suite.name,
                )
            raise ArchiveImportError(
                'Unable to import binary package `{}/{}/{}`: Could not find corresponding source package ({}).'.format(
                    pkgname, version, pkgarch, search_msg
                )
            )

        if is_new:
            if bpkg in self._session:
                self._session.delete(bpkg)
            self._session.expunge(bpkg)

        # fetch component this binary package is in
        component = self._session.query(ArchiveComponent).filter(ArchiveComponent.name == component_name).one_or_none()
        if component:
            if component not in deb_rss.suite.components:
                raise ArchiveImportError(
                    'Unable to import binary package `{}/{}/{}`: Archive component `{}` does not exist in `{}:{}`.'.format(
                        pkgname, version, pkgarch, component.name, deb_rss.repo.name, deb_rss.suite.name
                    )
                )
        else:
            if component_name == 'main':
                raise ArchiveImportError(
                    'Unable to import binary package `{}/{}/{}`: Archive component `{}` is missing.'.format(
                        pkgname, version, pkgarch, component_name
                    )
                )
            else:
                # We do not have the desired component *at all* - this may be the case if we do
                # support 'main', but not 'contrib', and if a source package in 'main' has built
                # binaries for 'contrib'. In that case, we simply drop the binary package semi-silently
                # and do emit a warning.
                archive_log.info(
                    'BINPKG-IMPORT-IGNORED: %s/%s/%s @ %s:%s/%s',
                    pkgname,
                    version,
                    pkgarch,
                    deb_rss.repo.name,
                    deb_rss.suite.name,
                    component_name,
                )
                log.warning(
                    'Ignored import request for binary `%s/%s/%s`: Archive component `%s` does not exist.',
                    pkgname,
                    version,
                    pkgarch,
                    component.name,
                )
                if bpkg in self._session:
                    self._session.delete(bpkg)
                self._session.expunge(bpkg)
                return None

        # find pool location
        if is_new:
            # for NEW stuff, we move the binary next to the source into its component
            pool_dir = pool_dir_from_name_component(bpkg.source.name, bpkg.source.component.name)
        else:
            # if we are not NEW, the binary goes into its proper place
            pool_dir = pool_dir_from_name_component(bpkg.source.name, component.name)
        deb_basename = '{}_{}_{}.{}'.format(
            bpkg.name, split_epoch(bpkg.version)[1], bpkg.architecture.name, str(pkg_type)
        )
        pool_fname = os.path.join(pool_dir, deb_basename)

        # configure package file
        af = ArchiveFile(pool_fname, deb_rss.repo)
        af.size = bin_tf.pop('Size')
        af.md5sum = bin_tf.pop('MD5sum')
        af.sha1sum = bin_tf.pop('SHA1')
        af.sha256sum = bin_tf.pop('SHA256')
        af.sha512sum = bin_tf.pop('SHA512', None)

        # ensure checksums match
        verify_hashes(af, deb_fname)
        if is_new:
            # if this binary belongs to a package in the NEW queue, we don't register it and just move the binary
            # alongside the source package
            pool_fname_full = os.path.join(self._repo_newqueue_root, af.fname)
            self._copy_or_move(deb_fname, pool_fname_full, override=True)

            log.info(
                'Binary `{}/{}` for {}/{} added to NEW queue'.format(
                    bpkg.name, bpkg.version, deb_rss.repo.name, deb_rss.suite.name
                )
            )
            # nothing left to do, we will not register this package with the database
            return bpkg
        else:
            pool_fname_full = os.path.join(deb_rss.repo.get_root_dir(), af.fname)

        bpkg.bin_file = af
        bpkg.description = safe_strip(bin_tf.pop('Description'))
        bpkg.summary = bpkg.description.split('\n', 1)[0].strip()
        bpkg.description_md5 = hashlib.md5(str(bpkg.description).encode('utf-8')).hexdigest()

        # we don't need the generated filename value
        bin_tf.pop('Filename')
        # we fetch those from already added overrides
        bin_tf.pop('Priority', None)
        bin_tf.pop('Section')
        bin_tf.pop('Essential', None)

        # check for override
        override = (
            self._session.query(PackageOverride)
            .filter(
                PackageOverride.repo_id == deb_rss.repo_id,
                PackageOverride.suite_id == deb_rss.suite_id,
                PackageOverride.pkg_name == bpkg.name,
            )
            .one_or_none()
        )
        if not override:
            if is_debug_pkg:
                # we have a debug package, so we can auto-generate a new override
                override = PackageOverride(bpkg.name)
                override.repo = deb_rss.repo
                override.suite = deb_rss.suite
                override.component = component
                override.section = self._session.query(ArchiveSection).filter(ArchiveSection.name == 'debug').one()
                override.priority = PackagePriority.OPTIONAL
            elif ignore_missing_override:
                # The override is missing, but we are supposed to ignore that fact.
                # So we will try our very best to guess a sensible override for this binary.

                # Try to copy an override from another suite in the same repository.
                eov = (
                    self._session.query(PackageOverride)
                    .filter(
                        PackageOverride.repo_id == bpkg.repo_id,
                        PackageOverride.pkg_name == bpkg.name,
                    )
                    .first()
                )

                if eov:
                    log.warning(
                        'Copying override from other suite for %s in %s:%s.',
                        bpkg.name,
                        bpkg.repo.name,
                        deb_rss.suite.name,
                    )
                    override = PackageOverride(bpkg.name)
                    override.repo = bpkg.repo
                    override.suite = deb_rss.suite
                    override.essential = eov.essential
                    override.priority = eov.priority
                    override.component = eov.component
                    override.section = eov.section
                    self._session.add(override)
                else:
                    # we just make up an override from scratch now
                    log.warning(
                        'No override found at all for %s in %s:%s, inventing one from scratch.',
                        bpkg.name,
                        bpkg.repo.name,
                        deb_rss.suite,
                    )
                    override = PackageOverride(bpkg.name)
                    override.repo = bpkg.repo
                    override.suite = deb_rss.suite
                    override.essential = False
                    override.component = bpkg.component
                    override.section = bpkg.source.section
                    self._session.add(override)
            else:
                raise ArchiveImportError(
                    'Missing override for `{}/{}`: Please process the source package through NEW first before uploading a binary.'.format(
                        pkgname, version
                    )
                )

        # add component
        bpkg.component = component

        # process contents list
        bpkg.contents = [line.split('\t', 1)[0] for line in filelist_raw]

        bpkg.depends = pop_split(bin_tf, 'Depends', ',')
        bpkg.pre_depends = pop_split(bin_tf, 'Pre-Depends', ',')

        bpkg.replaces = pop_split(bin_tf, 'Replaces', ',')
        bpkg.provides = pop_split(bin_tf, 'Provides', ',')
        bpkg.recommends = pop_split(bin_tf, 'Recommends', ',')
        bpkg.suggests = pop_split(bin_tf, 'Suggests', ',')
        bpkg.enhances = pop_split(bin_tf, 'Enhances', ',')
        bpkg.conflicts = pop_split(bin_tf, 'Conflicts', ',')
        bpkg.breaks = pop_split(bin_tf, 'Breaks', ',')

        bpkg.built_using = pop_split(bin_tf, 'Built-Using', ',')
        bpkg.static_built_using = pop_split(bin_tf, 'Static-Built-Using', ',')
        bpkg.build_ids = pop_split(bin_tf, 'Build-Ids', ' ')
        bpkg.multi_arch = safe_strip(bin_tf.pop('Multi-Arch', None))

        # add to target suite
        bpkg.suites.append(deb_rss.suite)

        # add (custom) fields that we did no account for
        bpkg.extra_data = dict(bin_tf)

        # copy files and register binary
        if os.path.exists(pool_fname_full):
            raise ArchiveImportError('Destination source file `{}` already exists. Can not continue'.format(af.fname))
        self._copy_or_move(deb_fname, pool_fname_full)

        self._session.add(af)
        self._session.add(bpkg)

        package_mark_published(self._session, deb_rss, bpkg)
        deb_rss.changes_pending = True
        log.info('Added binary `{}/{}` to {}/{}'.format(bpkg.name, bpkg.version, deb_rss.repo.name, deb_rss.suite.name))
        self._session.commit()

        return bpkg


@dataclass
class UploadChangesResult:
    success: bool
    uploader: ArchiveUploader
    spkg: SourcePackage | None = None
    is_new: bool = False
    target_suite_name: str | None = None
    error: str | None = None


class UploadHandler:
    """
    Verifies an upload and admits it to the archive if basic checks pass.
    """

    def __init__(self, session, repo: ArchiveRepository, event_emitter: T.Optional[EventEmitter] = None):
        self._session = session
        self._repo = repo
        self._emitter = event_emitter

        self._lconf = LocalConfig()
        if not self._emitter:
            self._emitter = EventEmitter(LkModule.ARCHIVE)
        self._lintian_conf = LintianConfig()

        self.keep_source_packages = False
        self.auto_emit_reject = True
        self.skip_lintian_check = False

        self._suite_map: T.Dict[str, str] = self._repo.upload_suite_map
        if not self._suite_map:
            self._suite_map = {}

        if not shutil.which('bwrap') or not shutil.which('lintian'):
            raise RuntimeError('Could not find Bubblewrap or Lintian. Please ensure both tools are installed.')

    def _add_uploader_event_data(self, event_data: T.Dict[str, str], uploader: T.Optional[ArchiveUploader]):
        """Add relevant uploader data to the event data"""
        if not uploader:
            return
        event_data['uploader_email'] = uploader.email
        if uploader.name:
            event_data['uploader_name'] = uploader.name
        if uploader.alias:
            event_data['uploader_alias'] = uploader.alias

    def emit_package_upload_rejected(
        self,
        changes_fname: T.PathUnion,
        reason: str,
        uploader: T.Optional[ArchiveUploader],
    ):
        """Emit a message-stream reject message for this package upload."""

        event_data = {'repo': self._repo.name, 'upload_name': Path(changes_fname).stem, 'reason': reason}
        self._add_uploader_event_data(event_data, uploader)
        self._emitter.submit_event_for_mod(LkModule.ARCHIVE, 'package-upload-rejected', event_data)
        archive_log.info(
            'UPLOAD_REJECT: %s @ %s: %s', event_data['upload_name'], event_data['repo'], event_data['reason']
        )

    def _process_changes_internal(self, fname: T.PathUnion) -> UploadChangesResult:
        """Version of :func:`process_changes` that will not emit message stream messages"""
        from glob import glob

        changes = parse_changes(
            fname,
            keyrings=list(glob(os.path.join(self._lconf.uploaders_keyring_dir, 'pubring.kbx'))),
            require_signature=True,
        )

        uploader: ArchiveUploader | None = (
            self._session.query(ArchiveUploader)
            .filter(ArchiveUploader.pgp_fingerprints.any(changes.primary_fingerprint))
            .one_or_none()
        )
        if not uploader:
            raise UploadError(
                'Unable to find registered uploader for fingerprint "{}" for "{}"'.format(
                    changes.primary_fingerprint, os.path.basename(fname)
                )
            )

        if changes.weak_signature:
            return UploadChangesResult(
                False,
                uploader,
                error='The GPG signature on {} is weak, please sign the upload with a stronger key.'.format(
                    os.path.basename(fname)
                ),
            )

        if len(changes.distributions) != 1:
            return UploadChangesResult(
                False,
                uploader,
                error=(
                    'Invalid amount of distributions set in this changes file. '
                    'We currently can only handle exactly one target (got {}).'
                ).format(str(changes.distributions)),
            )
        suite_name = changes.distributions[0]
        # override target suite based on the repository's suite mapping
        if suite_name in self._suite_map:
            suite_name = self._suite_map[suite_name]

        if changes.sourceful and not uploader.allow_source_uploads:
            return UploadChangesResult(
                False,
                uploader,
                error='This uploader is not permitted to make sourceful uploads to {}.'.format(
                    str(changes.distributions)
                ),
            )

        # fetch the repository-suite config for this package
        rss = (
            self._session.query(ArchiveRepoSuiteSettings)
            .filter(
                ArchiveRepoSuiteSettings.repo.has(id=self._repo.id),
                ArchiveRepoSuiteSettings.suite.has(name=suite_name),
            )
            .one()
        )

        if rss.frozen:
            return UploadChangesResult(
                False,
                uploader,
                error='Can not accept new upload for frozen suite {} of {}.'.format(rss.suite.name, rss.repo.name),
            )
        if not rss.accept_uploads:
            return UploadChangesResult(
                False,
                uploader,
                error='Can not accept new upload for suite {} of {}: The suite does not permit uploads.'.format(
                    rss.suite.name, rss.repo.name
                ),
            )

        result = (
            self._session.query(ArchiveVersionMemory.highest_version)
            .filter(
                ArchiveVersionMemory.repo_suite_id == rss.id,
                ArchiveVersionMemory.pkg_name == changes.source_name,
                ArchiveVersionMemory.arch_name == 'source',
                ArchiveVersionMemory.highest_version >= changes.changes['Version'],
            )
            .one_or_none()
        )
        if changes.sourceful and result:
            return UploadChangesResult(
                False,
                uploader,
                error=(
                    'Your upload contains version "{}" of source package "{}", however we have already seen a '
                    'higher or equal version in {}:{} before.\n'
                    'Uploads must have a higher version than already present in the archive.'
                ).format(result[0], changes.source_name, rss.repo.name, rss.suite.name),
            )

        # FIXME: We should maybe also preemptively check the binaries and their versions here,
        #  rather than possibly uncleanly failing at a later stage.
        # At the moment there is a chance that we partially import the package, if any kind of failure
        # happens at a later stage.

        try:
            files = changes.files
        except InvalidChangesError as e:
            return UploadChangesResult(
                False,
                uploader,
                error='This changes file was invalid: {}.'.format(str(e)),
            )

        if not uploader.allow_binary_uploads:
            for file in files.values():
                if is_deb_file(file.fname):
                    return UploadChangesResult(
                        False,
                        uploader,
                        error='This uploader is not allowed to upload binaries. Please upload a source-only package!.',
                    )

        # create a temporary scratch location to copy the files of this upload to.
        orig_changes_dir = changes.directory
        with tempfile.TemporaryDirectory(prefix='lk-pkgupload_') as tmp_dir:
            hash_issues = []
            for file in files.values():
                fname_src = os.path.join(orig_changes_dir, os.path.basename(file.fname))
                fname_dst = os.path.join(tmp_dir, os.path.basename(file.fname))

                shutil.copy(fname_src, fname_dst)
                shutil.chown(fname_dst, user=os.getuid(), group=os.getgid())
                os.chmod(fname_dst, 0o755)

                # verify checksum
                # validate hashes mentioned in the changes file
                try:
                    verify_hashes(file, fname_dst)
                except HashVerifyError as e:
                    hash_issues.append(e)

            # copy the changes file itself
            changes_fname_dst = os.path.join(tmp_dir, changes.filename)
            shutil.copy(fname, changes_fname_dst)
            shutil.chown(fname_dst, user=os.getuid(), group=os.getgid())
            os.chmod(fname_dst, 0o755)

            # fail here (after the data has been moved out of the way or copied)
            # in case there were any hash issues found
            if hash_issues:
                return UploadChangesResult(
                    False,
                    uploader,
                    error='Upload failed due to a checksum issue: {}'.format('\n'.join([str(e) for e in hash_issues])),
                )

            # adjust for moved changes file
            changes.directory = tmp_dir

            # actually perform final checks and import the package into the archive
            try:
                is_new, spkg = self._import_trusted_changes(rss, changes, uploader)
            except (ArchiveImportError, UploadError) as e:
                return UploadChangesResult(False, uploader, error=str(e))

            # everything went fine
            if not self.keep_source_packages:
                for file in files.values():
                    fname_src = os.path.join(orig_changes_dir, os.path.basename(file.fname))
                    os.unlink(fname_src)
                os.unlink(fname)

        # if we are here, everything went fine and the package is in the archive or NEW now
        return UploadChangesResult(True, uploader, is_new=is_new, spkg=spkg, target_suite_name=suite_name)

    def _import_trusted_changes(
        self,
        rss: ArchiveRepoSuiteSettings,
        changes: Changes,
        uploader: ArchiveUploader,
    ) -> tuple[bool, SourcePackage | None]:
        """This function will import changes from a trusted source.
        We assume that the upload is residing in a temporary scratch space that we can modify and that can not be
        modified by any other party.
        This function is only to be called internally.
        """

        # first do some last verification and validation steps
        files: T.Dict[str, ChangesFileEntry] = changes.files
        dsc_cfe: ChangesFileEntry | None = None
        for file in files.values():
            # jump to the dsc file
            if not file.fname.endswith('.dsc'):
                continue
            dsc_cfe = file
            # there should only be one source package per changes file
            break

        if dsc_cfe:
            # we have a source package in the upload!

            if '/' in dsc_cfe.fname:
                raise UploadError('Invalid source package filename: {}'.format(str(dsc_cfe.fname)))

            # check for orig tarball
            has_orig_tar = False
            for cf in files.values():
                if re_file_orig.match(os.path.basename(cf.fname)):
                    has_orig_tar = True

            if not has_orig_tar:
                # We have no orig.tar.* file - this may be okay if we already have the same upstream version in
                # the archive which provides this file, so let's look for it!
                # In case this is a native package, the dsc file will not have an orig reference, and we will just
                # skip this section automatically.
                with open(os.path.join(changes.directory, dsc_cfe.fname), 'r') as f:
                    dsc = Sources(f)
                    dsc_files = checksums_list_to_file(dsc.get('Checksums-Sha1'), 'sha1')
                    dsc_files = checksums_list_to_file(dsc.get('Checksums-Sha256'), 'sha256', dsc_files)
                for dscf_basename, dsc_f in dsc_files.items():
                    if re_file_orig.match(dscf_basename):
                        orig_poolname = os.path.join(
                            pool_dir_from_name_component(dsc.get('Source'), dsc_cfe.component), dscf_basename
                        )
                        afile_orig = (
                            self._session.query(ArchiveFile)
                            .filter(
                                ArchiveFile.fname == orig_poolname,
                                ArchiveFile.sha1sum == dsc_f.sha1sum,
                                ArchiveFile.sha256sum == dsc_f.sha256sum,
                            )
                            .one_or_none()
                        )
                        if not afile_orig:
                            afile_orig_nocs = (
                                self._session.query(ArchiveFile)
                                .filter(ArchiveFile.fname == orig_poolname)
                                .one_or_none()
                            )
                            if afile_orig_nocs:
                                raise UploadError(
                                    (
                                        'Referenced upstream source checksums for `{}` do not match the ones of the '
                                        'version found in the archive.'
                                    ).format(dscf_basename)
                                )
                            else:
                                raise UploadError(
                                    'Unable to find upstream source `{}`. Please include it in the upload.'.format(
                                        dscf_basename
                                    )
                                )
                        else:
                            # copy to our scratch dir so apt-ftparchive will find this file later.
                            # we will also verify the checksum again for this file
                            hardlink_or_copy(
                                os.path.join(rss.repo.get_root_dir(), afile_orig.fname),
                                os.path.join(changes.directory, dscf_basename),
                            )

        # validate the new upload with Lintian
        if not self.skip_lintian_check:
            lint_success, lintian_tags = lintian_check(
                os.path.join(changes.directory, changes.filename), tags=self._lintian_conf.fatal_tags
            )
            if not lint_success:
                lintian_lines = []
                for tag in lintian_tags:
                    lintian_lines.append('{}: {}: {}'.format(tag['level'], tag['tag'], tag['description']))
                raise UploadError(
                    ('Unable to process upload {}: Lintian issues were found, please resolve them.\n{}').format(
                        changes.filename, '\n'.join(lintian_lines)
                    )
                )

        # prepare package importer
        pi = PackageImporter(self._session, rss)
        pi.keep_source_packages = self.keep_source_packages
        changes_urgency = ChangesUrgency.from_string(changes.changes.get('Urgency', 'low'))  #

        # actually run the package import, starting with the source package (dsc file)
        spkg: SourcePackage | None = None
        is_new: bool = False
        if dsc_cfe:
            try:
                new_policy = rss.new_policy
                # uploader policy beats suite policy
                if uploader.always_review:
                    new_policy = NewPolicy.ALWAYS_NEW
                spkg, is_new = pi.import_source(
                    os.path.join(changes.directory, dsc_cfe.fname), dsc_cfe.component, new_policy=new_policy
                )
                spkg.changes_urgency = changes_urgency
                if is_new:
                    spkg_queue_dir = os.path.join(rss.repo.get_new_queue_dir(), spkg.directory)
                    shutil.copy(
                        os.path.join(changes.directory, changes.filename),
                        os.path.join(spkg_queue_dir, '{}_{}.changes'.format(spkg.name, spkg.version)),
                    )
            except Exception as e:
                raise UploadError('Failed to import source package: {}'.format(str(e)))

        # import binary packages
        for file in files.values():
            if is_deb_file(file.fname):
                if '/' in file.fname:
                    raise UploadError('Invalid binary package filename: {}'.format(str(file.fname)))
                try:
                    pi.import_binary(os.path.join(changes.directory, file.fname), file.component)
                except Exception as e:
                    raise UploadError('Failed to import binary package: {}'.format(str(e)))

        # looks like the package was accepted - spread the news!
        ev_data = {
            'repo': self._repo.name,
            'upload_name': Path(changes.filename).stem,
            'is_new': is_new,
            'files': list(files.keys()),
            'changes': changes.changes.get('Changes', 'Unknown changes'),
        }
        if spkg:
            ev_data['source_name'] = spkg.name
            ev_data['source_version'] = spkg.version
            ev_data['source_maintainer'] = spkg.maintainer
            ev_data['source_uploaders'] = spkg.uploaders
        self._add_uploader_event_data(ev_data, uploader)
        self._emitter.submit_event_for_mod(LkModule.ARCHIVE, 'package-upload-accepted', ev_data)
        archive_log.info(
            '%s: %s @ %s', 'UPLOAD-NEW' if is_new else 'UPLOAD-ACCEPTED', ev_data['upload_name'], self._repo.name
        )

        return is_new, spkg

    def process_changes(self, fname: T.PathUnion) -> UploadChangesResult:
        """
        Verify and import an upload by its .changes file.
        The caller should make sure the changes file is located at a safe location.
        :param fname: Path to the .changes file
        :return: A tuple of a boolean indication whether the changes file was processed successfully,
        the archive uploader this upload belongs to, and an optional string explaining the error reason in case of a failure.

        In case of irrecoverable issues (when no uploader can be determined or the signature is missing or invalid)
        an exception is thrown, otherwise a tuple consisting of the status, uploader and error message (if any) is returned.
        """

        try:
            result = self._process_changes_internal(fname)
        except Exception as e:
            if self.auto_emit_reject:
                self.emit_package_upload_rejected(fname, str(e), None)
            raise e
        if not result.success or result.error:
            if self.auto_emit_reject:
                self.emit_package_upload_rejected(fname, result.error, result.uploader)
        return result
