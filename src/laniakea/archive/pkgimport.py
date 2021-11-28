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

from laniakea.db import SourcePackage, ArchiveVersionMemory, ArchiveRepoSuiteSettings
from laniakea.archive.utils import checksums_list_to_file, parse_package_list_str


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

        pkgname = src_tf['Package']
        version = src_tf['Version']

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
        spkg.format_version = src_tf['Format']
        spkg.architectures = src_tf['Architecture'].split(' ')
        spkg.maintainer = src_tf['Maintainer']
        spkg.uploaders = src_tf.get('Uploaders', '').split(', ')

        spkg.build_depends = src_tf.get('Build-Depends', '').split(', ')
        spkg.build_depends_indep = src_tf.get('Build-Depends-Indep', '').split(', ')
        spkg.build_conflicts = src_tf.get('Build-Conflicts', '').split(', ')
        spkg.build_conflicts_indep = src_tf.get('Build-Conflicts-Indep', '').split(', ')
        spkg.expected_binaries = parse_package_list_str(src_tf['Package-List'])

        files = checksums_list_to_file(src_tf['Files'], 'md5')
        files = checksums_list_to_file(src_tf['Checksums-Sha1'], 'sha1', files)
        files = checksums_list_to_file(src_tf['Checksums-Sha256'], 'sha256', files)
        files = checksums_list_to_file(src_tf.get('Checksums-Sha512', None), 'sha512', files)

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

        self._session.add(spkg)
