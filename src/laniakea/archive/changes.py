# -*- coding: utf-8 -*-
#
# Copyright (C) 2012, Ansgar Burchardt <ansgar@debian.org>
# Copyright (C) 2020-2022 Matthias Klumpp <mak@debian.org>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import re
import functools
from typing import Any, Dict, List, Union, Optional

import apt_pkg

from laniakea.db import ArchiveFile
from laniakea.utils import check_filename_safe
from laniakea.utils.gpg import SignedFile
from laniakea.archive.utils import AptVersion
from laniakea.archive.pkgimport import UploadException

__all__ = [
    'InvalidChangesException',
    'Changes',
    'parse_changes',
]


class InvalidChangesException(UploadException):
    pass


class ParseChangesError(UploadException):
    "Exception raised for errors in parsing a changes file."


orig_source_ext_re = r"orig(?:-[a-zA-Z0-9-]+)?\.tar\.(?:gz|bz2|xz)(?:\.asc)?"
file_source_ext_re = "(" + orig_source_ext_re + r"|(?:debian\.)?tar\.(?:gz|bz2|xz)|diff\.gz)"

# Prefix of binary and source filenames
_re_file_prefix = r'^(?P<package>[a-z0-9][a-z0-9.+-]+)_(?P<version>[A-Za-z0-9.~+-]+?)'

# Match dsc files
# Groups: package, version
re_file_dsc = re.compile(_re_file_prefix + r'\.dsc$')

# Match other source files
# Groups: package, version
re_file_source = re.compile(_re_file_prefix + r'\.' + file_source_ext_re)

# Match buildinfo file
# Groups: package, version, suffix
re_file_buildinfo = re.compile(_re_file_prefix + r'_(?P<suffix>[a-zA-Z0-9+-]+)\.buildinfo$')

# Match source field
# Groups: package, version
re_field_source = re.compile(r'^(?P<package>[a-z0-9][a-z0-9.+-]+)(?:\s*\((?P<version>[A-Za-z0-9.:~+-]+)\))?$')

# Match binary packages
# Groups: package, version, architecture, type
re_file_binary = re.compile(_re_file_prefix + r'_(?P<architecture>[a-z0-9-]+)\.(?P<type>u?deb)$')


def parse_file_list(
    control: Union[apt_pkg.TagSection, Dict[Any, Any]],
    has_priority_and_section,
    fields=('Files', 'Checksums-Sha1', 'Checksums-Sha256'),
):
    """Parse Files and Checksums-* fields

    :param control: control file to take fields from
    :param has_priority_and_section: Files field include section and priority (as in .changes)
    :param fields:
    :raise InvalidChangesException: missing fields or other grave errors
    :return: dict mapping filenames to :ArchiveFile objects
    """
    entries = {}

    for line in control.get(fields[0], "").split('\n'):
        if len(line) == 0:
            continue

        if has_priority_and_section:
            (md5sum, size, section, priority, filename) = line.split()
            entry = dict(md5sum=md5sum, size=int(size), section=section, priority=priority, filename=filename)
        else:
            (md5sum, size, filename) = line.split()
            entry = dict(md5sum=md5sum, size=int(size), filename=filename)

        entries[filename] = entry

    for line in control.get(fields[1], "").split('\n'):
        if len(line) == 0:
            continue
        (sha1sum, size, filename) = line.split()
        entry = entries.get(filename, None)
        if entry is None:
            raise InvalidChangesException(
                '{0} is listed in {1}, but not in {2}.'.format(filename, fields[1], fields[0])
            )
        if entry is not None and entry.get('size', None) != int(size):
            raise InvalidChangesException(
                'Size for {0} in {1} and {2} fields differ.'.format(filename, fields[0], fields[1])
            )
        entry['sha1sum'] = sha1sum

    for line in control.get(fields[2], "").split('\n'):
        if len(line) == 0:
            continue
        (sha256sum, size, filename) = line.split()
        entry = entries.get(filename, None)
        if entry is None:
            raise InvalidChangesException(
                '{0} is listed in {1}, but not in {2}.'.format(filename, fields[2], fields[0])
            )
        if entry is not None and entry.get('size', None) != int(size):
            raise InvalidChangesException(
                'Size for {0} in {1} and {2} fields differ.'.format(filename, fields[0], fields[2])
            )
        entry['sha256sum'] = sha256sum

    files = {}
    for entry in entries.values():
        filename = str(entry['filename'])
        if 'size' not in entry:
            raise InvalidChangesException('No size for {0}.'.format(filename))
        if 'md5sum' not in entry:
            raise InvalidChangesException('No md5sum for {0}.'.format(filename))
        if 'sha1sum' not in entry:
            raise InvalidChangesException('No sha1sum for {0}.'.format(filename))
        if 'sha256sum' not in entry:
            raise InvalidChangesException('No sha256sum for {0}.'.format(filename))
        if not check_filename_safe(filename):
            raise InvalidChangesException("References file with unsafe filename {}.".format(filename))

        file = ArchiveFile(filename)
        file.size = entry['size']
        file.md5sum = entry['md5sum']
        file.sha1sum = entry['sha1sum']
        file.sha256sum = entry['sha256sum']
        if 'sha512sum' in entry:
            file.sha512sum = entry['sha512sum']
        files[filename] = file

    return files


class SourceInfo:
    """Brief information about a source package"""

    def __init__(self, directory: str, source_files):
        self.directory = directory
        self.source_files = source_files


class BinaryInfo:
    """Brief information about a source package"""

    def __init__(self, directory: str, file):
        self.directory = directory
        self.file = file


@functools.total_ordering
class Changes:
    """Representation of a .changes file"""

    def __init__(self, fname: Union[os.PathLike, str], keyrings, require_signature=True):
        filename = os.path.basename(fname)
        directory = os.path.abspath(os.path.dirname(fname))
        if not check_filename_safe(filename):
            raise InvalidChangesException('{0}: unsafe filename'.format(filename))

        self.directory = str(directory)
        """directory the .changes is located in"""

        self.filename = str(filename)
        """name of the .changes file"""

        with open(self.path, 'rb') as f:
            data = f.read()
        self.signature = SignedFile(data, keyrings=keyrings, require_signature=require_signature)

        self.changes = apt_pkg.TagSection(self.signature.contents)
        """dict to access fields of the .changes file"""

        self._binaries: Optional[List[BinaryInfo]] = None
        self._source: Optional[SourceInfo] = None
        self._files: Optional[Dict[str, ArchiveFile]] = None
        self._keyrings = keyrings
        self._require_signature = require_signature

    @property
    def path(self) -> str:
        """path to the .changes file"""
        return os.path.join(self.directory, self.filename)

    @property
    def primary_fingerprint(self) -> str:
        """fingerprint of the key used for signing the .changes file"""
        return self.signature.primary_fingerprint

    @property
    def valid_signature(self) -> bool:
        """C{True} if the .changes has a valid signature"""
        return self.signature.valid

    @property
    def weak_signature(self) -> bool:
        """C{True} if the .changes was signed using a weak algorithm"""
        return self.signature.weak_signature

    @property
    def signature_timestamp(self):
        return self.signature.signature_timestamp

    @property
    def contents_sha1(self):
        return self.signature.contents_sha1

    @property
    def architectures(self) -> List[str]:
        """list of architectures included in the upload"""
        return self.changes.get('Architecture', '').split()

    @property
    def distributions(self) -> List[str]:
        """list of target distributions for the upload"""
        return self.changes['Distribution'].split()

    @property
    def source(self) -> Optional[SourceInfo]:
        """Included source or None"""
        if self._source is None:
            source_files = []
            for f in self.files.values():
                if re_file_dsc.match(f.filename) or re_file_source.match(f.filename):
                    source_files.append(f)
            if len(source_files) > 0:
                self._source = SourceInfo(self.directory, source_files)
        return self._source

    @property
    def sourceful(self) -> bool:
        """True if the upload includes source"""
        return "source" in self.architectures

    @property
    def source_name(self) -> str:
        """source package name"""
        return re_field_source.match(self.changes['Source']).group('package')

    @property
    def binaries(self) -> Optional[List[BinaryInfo]]:
        """included binary packages"""
        if self._binaries is None:
            binaries = []
            for f in self.files.values():
                if re_file_binary.match(f.filename):
                    binaries.append(BinaryInfo(self.directory, f))
            self._binaries = binaries
        return self._binaries

    @property
    def byhand_files(self) -> List[ArchiveFile]:
        """included byhand files"""
        byhand = []

        for f in self.files.values():
            if f.section == 'byhand' or f.section[:4] == 'raw-':
                byhand.append(f)
                continue
            if re_file_dsc.match(f.filename) or re_file_source.match(f.filename) or re_file_binary.match(f.filename):
                continue
            if re_file_buildinfo.match(f.filename):
                continue

            raise InvalidChangesException(
                "{0}: {1} looks like a byhand package, but is in section {2}".format(
                    self.filename, f.filename, f.section
                )
            )

        return byhand

    @property
    def buildinfo_files(self) -> List[ArchiveFile]:
        """included buildinfo files"""
        buildinfo = []

        for f in self.files.values():
            if re_file_buildinfo.match(f.filename):
                buildinfo.append(f)

        return buildinfo

    @property
    def binary_names(self) -> List[str]:
        """names of included binary packages"""
        return self.changes.get('Binary', '').split()

    @property
    def closed_bugs(self) -> List[str]:
        """bugs closed by this upload"""
        return self.changes.get('Closes', '').split()

    @property
    def files(self) -> Dict[str, ArchiveFile]:
        """dict mapping filenames to :ArchiveFile objects"""
        if self._files is None:
            self._files = parse_file_list(self.changes, True)
        return self._files

    @property
    def bytes(self) -> int:
        """total size of files included in this upload in bytes"""
        count = 0
        for f in self.files.values():
            count += f.size
        return count

    def _key(self):
        """tuple used to compare two changes files

        We sort by source name and version first.  If these are identical,
        we sort changes that include source before those without source (so
        that sourceful uploads get processed first), and finally fall back
        to the filename (this should really never happen).

        :rtype:  tuple
        """
        return (
            self.changes.get('Source'),
            AptVersion(self.changes.get('Version', '')),
            not self.sourceful,
            self.filename,
        )

    def __eq__(self, other):
        return self._key() == other._key()

    def __lt__(self, other):
        return self._key() < other._key()


def parse_changes(filename, *, keyrings=None, require_signature=True) -> Changes:
    """
    Parses a changes file and returns a :Changes instance. The mandatory first argument
    is the filename of the .changes file.
    """

    changes = Changes(filename, keyrings=keyrings, require_signature=require_signature)
    # Finally ensure that everything needed for .changes is there
    must_keywords = (
        'Format',
        'Date',
        'Source',
        'Architecture',
        'Version',
        'Distribution',
        'Maintainer',
        'Changes',
        'Files',
    )

    missing_fields = []
    for keyword in must_keywords:
        if keyword.lower() not in changes.changes:
            missing_fields.append(keyword)

            if len(missing_fields):
                raise ParseChangesError(
                    "Missing mandatory field(s) in changes file (policy 5.5): {}".format(missing_fields)
                )

    return changes
