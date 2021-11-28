# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import shutil
import hashlib
import subprocess
from typing import Union
from pathlib import Path

from apt_pkg import Hashes
from debian.deb822 import Sources, Packages

from laniakea.db import (
    DebType,
    ArchiveFile,
    PackageInfo,
    BinaryPackage,
    SourcePackage,
    PackageOverride,
    ArchiveComponent,
    ArchiveArchitecture,
    ArchiveQueueNewEntry,
    ArchiveVersionMemory,
    ArchiveRepoSuiteSettings,
)
from laniakea.logging import log
from laniakea.archive.utils import (
    split_epoch,
    pool_dir_from_name,
    check_overrides_source,
    checksums_list_to_file,
    parse_package_list_str,
    register_package_overrides,
)


class ArchiveImportError(Exception):
    """Import of a package into the archive failed."""


class PackageImporter:
    """Imports packages into the archive."""

    def __init__(self, session, repo_suite_settings: ArchiveRepoSuiteSettings):
        self._session = session
        self._rss = repo_suite_settings

        self._repo_root = self._rss.repo.get_root_dir()
        self._repo_newqueue_root = self._rss.repo.get_new_queue_dir()
        os.makedirs(self._repo_newqueue_root, exist_ok=True)

        self.keep_source_packages = False

    def copy_or_move(self, src, dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(src, dst)
        if not self.keep_source_packages:
            os.unlink(src)

    def import_source(self, dsc_fname: Union[Path, str], component_name: str = None, *, skip_new: bool = False):
        """Import a source package into the given suite or its NEW queue.

        :param dsc_fname: Path to a source package to import
        :param component_name: Name of the archive component to import into.
        :param skip_new: True if the NEW queue should be skipped and overrides be added automatically.
        """

        dsc_dir = os.path.dirname(dsc_fname)

        p = subprocess.run(
            ['apt-ftparchive', '-q', 'sources', dsc_fname], capture_output=True, check=True, encoding='utf-8'
        )
        src_tf = Sources(p.stdout)

        pkgname = src_tf.pop('Package')
        version = src_tf.pop('Version')

        result = (
            self._session.query(ArchiveVersionMemory.highest_version)
            .filter(
                ArchiveVersionMemory.repo_id == self._rss.repo_id,
                ArchiveVersionMemory.pkgname == pkgname,
                ArchiveVersionMemory.highest_version > version,
            )
            .one_or_none()
        )
        if result:
            raise ArchiveImportError(
                'Unable to import package "{}": '
                'We have already seen higher version "{}" in this repository before.'.format(pkgname, result)
            )

        spkg = SourcePackage(pkgname, version, self._rss.repo)
        spkg.format_version = src_tf.pop('Format')
        spkg.architectures = src_tf.pop('Architecture').split(' ')
        spkg.maintainer = src_tf.pop('Maintainer')
        spkg.uploaders = src_tf.pop('Uploaders', '').split(', ')

        spkg.build_depends = src_tf.pop('Build-Depends', '').split(', ')
        spkg.build_depends_indep = src_tf.pop('Build-Depends-Indep', '').split(', ')
        spkg.build_conflicts = src_tf.pop('Build-Conflicts', '').split(', ')
        spkg.build_conflicts_indep = src_tf.pop('Build-Conflicts-Indep', '').split(', ')
        if 'Package-List' in src_tf:
            spkg.expected_binaries = parse_package_list_str(src_tf.pop('Package-List'))
            src_tf.pop('Binary')
        else:
            log.warning(
                'Source package dsc file `{}/{}` had no `Package-List` '
                '- falling back to parsing `Binaries`.'.format(pkgname, version)
            )
            binary_stubs = []
            for b in src_tf.pop('Binary').split(', '):
                pi = PackageInfo()
                pi.name = b
                binary_stubs.append(pi)
            spkg.expected_binaries = binary_stubs

        component = self._session.query(ArchiveComponent).filter(ArchiveComponent.name == component_name).one()
        spkg.component = component

        spkg.directory = pool_dir_from_name(pkgname)
        files = checksums_list_to_file(src_tf.pop('Files'), 'md5')
        files = checksums_list_to_file(src_tf.pop('Checksums-Sha1'), 'sha1', files)
        files = checksums_list_to_file(src_tf.pop('Checksums-Sha256'), 'sha256', files)
        files = checksums_list_to_file(src_tf.pop('Checksums-Sha512', None), 'sha512', files)

        files_todo = []
        for file in files.values():
            file.srcpkg = spkg
            hashes_checked = 0

            with open(os.path.join(dsc_dir, file.fname), 'rb') as f:
                # pylint: disable=not-an-iterable
                for hash in Hashes(f).hashes:  # type: ignore
                    if hash.hashtype == 'MD5Sum':
                        hash_okay = file.md5sum == hash.hashvalue
                    elif hash.hashtype == 'SHA1':
                        hash_okay = file.sha1sum == hash.hashvalue
                    elif hash.hashtype == 'SHA256':
                        hash_okay = file.sha256sum == hash.hashvalue
                    elif hash.hashtype == 'SHA512':
                        hash_okay = file.sha512sum == hash.hashvalue
                    elif hash.hashtype == 'Checksum-FileSize':
                        hash_okay = file.size == hash.hashvalue
                    else:
                        raise ArchiveImportError(
                            'Unknown hash type "{}" - Laniakea likely needs to be adjusted to a new APT version.'.format(
                                hash.hashtype
                            )
                        )
                    if not hash_okay:
                        raise ArchiveImportError(
                            '{} checksum validation of "{}" failed (expected {}).'.format(
                                hash.hashtype, file.fname, hash.hashvalue
                            )
                        )
                    hashes_checked += 1
            if hashes_checked < 4:
                raise ArchiveImportError('An insufficient amount of hashes was validated for "{}" - this is a bug.')

            pool_fname = os.path.join(spkg.directory, file.fname)
            file.fname = pool_fname
            file.repo = self._rss.repo
            files_todo.append(file)

        missing_overrides = check_overrides_source(self._session, self._rss, spkg)
        if skip_new:
            # if we are supposed to skip NEW, we just register the overrides and add the package
            # to its designated suite
            register_package_overrides(self._session, self._rss, missing_overrides)
            spkg.suites.append(self._rss.suite)
            is_new = False
        else:
            if missing_overrides:
                # add to NEW queue
                nq_entry = ArchiveQueueNewEntry()
                nq_entry.package = spkg
                nq_entry.destination = self._rss.suite
                self._session.add(nq_entry)
                is_new = True
            else:
                # no missing overrides, the package is good to go
                spkg.suites.append(self._rss.suite)
                is_new = False

        for file in files_todo:
            if is_new:
                # move package to the NEW queue
                pool_fname_full = os.path.join(self._repo_newqueue_root, file.fname)
            else:
                # move package to the archive pool
                pool_fname_full = os.path.join(self._repo_root, file.fname)

            if os.path.exists(pool_fname_full):
                raise ArchiveImportError(
                    'Destination source file `{}` already exists. Can not continue'.format(file.fname)
                )
            self.copy_or_move(os.path.join(dsc_dir, os.path.basename(file.fname)), pool_fname_full)
            self._session.add(file)

        # drop directory key, we don't need it
        src_tf.pop('Directory')

        # store any remaining fields as extra data
        log.debug('Extra data fields for `{}/{}`: {}'.format(pkgname, version, dict(src_tf)))
        spkg.extra_data = dict(src_tf)

        self._session.add(spkg)

    def import_binary(self, deb_fname: Union[Path, str], component_name: str = None):
        """Import a binary package into the given suite or its NEW queue.

        :param deb_fname: Path to a deb/udeb package to import
        :param component_name: Name of the archive component to import into.
        """

        # deb_dir = os.path.dirname(deb_fname)
        pkg_type = DebType.DEB
        if os.path.splitext(deb_fname)[1] == '.udeb':
            pkg_type = DebType.UDEB

        p = subprocess.run(
            ['apt-ftparchive', '-q', 'packages', deb_fname], capture_output=True, check=True, encoding='utf-8'
        )
        bin_tf = Packages(p.stdout)

        p = subprocess.run(
            ['apt-ftparchive', '-q', 'contents', deb_fname], capture_output=True, check=True, encoding='utf-8'
        )
        filelist_raw = p.stdout.splitlines()

        pkgname = bin_tf.pop('Package')
        version = bin_tf.pop('Version')
        bpkg = BinaryPackage(pkgname, version, self._rss.repo)

        bpkg.architecture = (
            self._session.query(ArchiveArchitecture)
            .filter(ArchiveArchitecture.name == bin_tf.pop('Architecture'))
            .one()
        )
        bpkg.update_uuid()

        bpkg.maintainer = bin_tf.pop('Maintainer')
        bpkg.size_installed = bin_tf.pop('Installed-Size')

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

        # find the source package
        is_new = False
        bpkg.source = (
            self._session.query(SourcePackage)
            .filter(
                SourcePackage.repo_id == self._rss.repo_id,
                SourcePackage.suites.any(id=self._rss.suite_id),
                SourcePackage.name == source_name,
                SourcePackage.version == source_version,
            )
            .one_or_none()
        )
        if not bpkg.source:
            # maybe the package is in NEW?
            bpkg.source = (
                self._session.query(ArchiveQueueNewEntry.package)
                .filter(
                    ArchiveQueueNewEntry.destination_id == self._rss.suite_id,
                    ArchiveQueueNewEntry.package.has(name=source_name),
                    ArchiveQueueNewEntry.package.has(version=source_version),
                    ArchiveQueueNewEntry.package.has(repo_id=self._rss.repo_id),
                )
                .one_or_none()
            )
            if not bpkg.source:
                raise ArchiveImportError(
                    'Unable to import binary package `{}/{}`: Could not find corresponding source package.'.format(
                        pkgname, version
                    )
                )
            is_new = True

        pool_dir = pool_dir_from_name(bpkg.source.name)
        deb_fname = '{}_{}_{}.{}'.format(bpkg.name, split_epoch(bpkg.version)[1], bpkg.architecture.name, str(pkg_type))
        pool_fname = os.path.join(pool_dir, deb_fname)

        af = ArchiveFile(pool_fname)
        af.size = bin_tf.pop('Size')
        af.md5sum = bin_tf.pop('MD5sum')
        af.sha1sum = bin_tf.pop('SHA1')
        af.sha256sum = bin_tf.pop('SHA256')
        af.sha512sum = bin_tf.pop('SHA512', None)

        bpkg.description = bin_tf.pop('Description')
        bpkg.summary = bpkg.description.split('\n', 1)[0].strip()
        bpkg.description_md5 = hashlib.md5(bpkg.description.encode('utf-8')).hexdigest()

        # we don't need the generated filename value
        bin_tf.pop('Filename')
        # we fetch those from already added overrides
        bin_tf.pop('Priority')
        bin_tf.pop('Section')
        bin_tf.pop('Essential', None)

        # check for override
        if not is_new:
            override = (
                self._session.query(PackageOverride)
                .filter(PackageOverride.repo_suite_id == self._rss.id, PackageOverride.pkgname == bpkg.name)
                .one_or_none()
            )
            if not override:
                raise ArchiveImportError(
                    'Missing override for `{}/{}`: Please process the source package through NEW first before uploading a binary.'.format(
                        pkgname, version
                    )
                )
            bpkg.override = override

        # add component
        bpkg.component = self._session.query(ArchiveComponent).filter(ArchiveComponent.name == component_name).one()

        # process contents list
        bpkg.contents = [line.split('\t', 1)[0] for line in filelist_raw]

        print(af.fname)
        print(bin_tf)
