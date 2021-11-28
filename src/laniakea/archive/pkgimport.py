# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import subprocess
from typing import Union
from pathlib import Path

from apt_pkg import Hashes
from debian.deb822 import Sources

from laniakea.db import (
    PackageInfo,
    SourcePackage,
    ArchiveComponent,
    ArchiveQueueNewEntry,
    ArchiveVersionMemory,
    ArchiveRepoSuiteSettings,
)
from laniakea.logging import log
from laniakea.archive.utils import (
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

    def import_source(self, dsc_fname: Union[Path, str], component_name: str = None, *, skip_new: bool = False):
        """Import a source package into the given suite or its NEW queue."""

        dsc_dir = os.path.dirname(dsc_fname)

        p = subprocess.run(['apt-ftparchive', 'sources', dsc_fname], capture_output=True, check=True, encoding='utf-8')
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

        files = checksums_list_to_file(src_tf.pop('Files'), 'md5')
        files = checksums_list_to_file(src_tf.pop('Checksums-Sha1'), 'sha1', files)
        files = checksums_list_to_file(src_tf.pop('Checksums-Sha256'), 'sha256', files)
        files = checksums_list_to_file(src_tf.pop('Checksums-Sha512', None), 'sha512', files)

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
            if hashes_checked < 3:
                raise ArchiveImportError('An insufficient amount of hashes was validated for "{}" - this is a bug.')

            self._session.add(file)

        missing_overrides = check_overrides_source(self._session, self._rss, spkg)
        if skip_new:
            # if we are supposed to skip NEW, we just register the overrides and add the package
            # to its designated suite
            register_package_overrides(self._session, self._rss, missing_overrides)
            spkg.suites.append(self._rss.suite)
        else:
            if missing_overrides:
                # add to NEW queue
                nq_entry = ArchiveQueueNewEntry()
                nq_entry.package = spkg
                nq_entry.destination = self._rss.suite
                self._session.add(nq_entry)
            else:
                # no missing overrides, the package is good to go
                spkg.suites.append(self._rss.suite)

        # drop directory key, we don't need it
        src_tf.pop('Directory')

        # store any remaining fields as extra data
        log.debug('Extra data fields for `{}/{}`: {}'.format(pkgname, version, dict(src_tf)))
        spkg.extra_data = dict(src_tf)

        self._session.add(spkg)
