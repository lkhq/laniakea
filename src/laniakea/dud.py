# -*- coding: utf-8 -*-
#
# Copyright (C) 2008 Jonny Lamb <jonny@debian.org>
# Copyright (C) 2010 Jan Dittberner <jandd@debian.org>
# Copyright (C) 2012 Arno Töll <arno@debian.org>
# Copyright (C) 2012 Paul Tagliamonte <paultag@debian.org>
# Copyright (C) 2014 Matthias Klumpp <mak@debian.org>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import hashlib

import firehose.model

import laniakea.typing as T
from laniakea.utils import deb822
from laniakea.utils.gpg import SignedFile


class DudFileException(Exception):
    pass


class Dud(object):
    def __init__(self, filename=None, string=None):
        if (filename and string) or (not filename and not string):
            raise TypeError

        if filename:
            self._absfile = os.path.abspath(filename)
            self._directory = os.path.dirname(self._absfile)
            self._basename = os.path.basename(self._absfile)
            self._data = deb822.Changes(open(self._absfile))
        else:
            self._absfile = None
            self._directory = ''
            self._basename = None
            self._data = deb822.Changes(string)

        if len(self._data) == 0:
            raise DudFileException('dud file could not be parsed.')

    def get_filename(self):
        '''
        Returns the filename from which the dud file was generated from.
        Please do note this is just the basename, not the entire full path, or
        even a relative path. For the absolute path to the changes file, please
        see :meth:`get_dud_file`.
        '''
        return self._basename

    def get_dud_file(self):
        '''
        Return the full, absolute path to the dud file. For just the
        filename, please see :meth:`get_filename`.
        '''
        return self._absfile

    def get_firehose(self):
        return firehose.model.Analysis.from_xml(open(self.get_firehose_file(), 'r'))

    def get_firehose_file(self):
        for item in self.get_files():
            if item.endswith('.firehose.xml'):
                return item

    def get_log_file(self):
        for item in self.get_files():
            if item.endswith('.log'):
                return item

    def get_files(self):
        ''' '''
        return [os.path.join(self._directory, z['name']) for z in self._data['Files']]

    def __getitem__(self, key):
        '''
        Returns the value of the rfc822 key specified.

        ``key``
            Key of data to request.
        '''
        return self._data[key]

    def __contains__(self, key):
        '''
        Returns whether the specified RFC822 key exists.

        ``key``
            Key of data to check for existence.
        '''
        return key in self._data

    def get(self, key, default=None):
        '''
        Returns the value of the rfc822 key specified, but defaults
        to a specific value if not found in the rfc822 file.

        ``key``
            Key of data to request.

        ``default``
            Default return value if ``key`` does not exist.
        '''
        return self._data.get(key, default)

    def validate(self, check_hash='sha256', keyring_dir: T.PathUnion | None = None):
        from glob import glob

        self.validate_checksums(check_hash)
        if keyring_dir:
            keyrings = list(glob(os.path.join(keyring_dir, 'pubring.kbx')))
            self.validate_signature(keyrings)

    def validate_signature(self, keyrings):
        '''
        Validate the GPG signature of a .dud file.
        '''

        with open(self.get_dud_file(), 'rb') as f:
            signature = SignedFile(f.read(), keyrings=keyrings, require_signature=True)
            return signature.primary_fingerprint

    def validate_checksums(self, check_hash='sha256'):
        '''
        Validate checksums for a package, using ``check_hack``'s type
        to validate the package.

        Valid ``check_hash`` types:

            * sha1
            * sha256
            * md5
            * md5sum
        '''
        for filename in self.get_files():
            if check_hash == 'sha1':
                hash_type = hashlib.sha1()
                checksums = self.get('Checksums-Sha1')
                field_name = 'sha1'
            elif check_hash == 'sha256':
                hash_type = hashlib.sha256()
                checksums = self.get('Checksums-Sha256')
                field_name = 'sha256'
            elif check_hash == 'md5':
                hash_type = hashlib.md5()
                checksums = self.get('Files')
                field_name = 'md5sum'

            changed_files = None
            for cf in checksums:
                if cf['name'] == os.path.basename(filename):
                    changed_files = cf
                    break
            if not changed_files:
                raise Exception('get_files() returns different files than Files: knows?!')

            with open(filename, 'rb') as fc:
                for chunk in iter((lambda fc=fc, hash_type=hash_type: fc.read(128 * hash_type.block_size)), b''):
                    hash_type.update(chunk)

            if not hash_type.hexdigest() == changed_files[field_name]:
                raise DudFileException(
                    'Checksum mismatch for file %s: %s != %s'
                    % (filename, hash_type.hexdigest(), changed_files[field_name])
                )
