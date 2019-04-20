# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2013 Paul Tagliamonte <paultag@debian.org>
# Copyright (C) 2014      Jon Severinsson <jon@severinsson.net>
#
# Licensed under the GNU Lesser General Public License Version 3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the license, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

from debian.deb822 import _gpg_multivalued
from debian.deb822 import Changes as Changes_
import hashlib
import os


# Copy of debian.deb822.Dsc with Package-List: support added.
class Dsc(_gpg_multivalued):
    _multivalued_fields = {
        'package-list': ['name', 'type', 'section', 'priority'],
        'files': ['md5sum', 'size', 'name'],
        'checksums-sha1': ['sha1', 'size', 'name'],
        'checksums-sha256': ['sha256', 'size', 'name'],
    }


# Extention to debian.deb822.Changes with add_file() support
# Also useful for Debile *.dud files.
class Changes(Changes_):
    def add_file(self, fp):
        statinfo = os.stat(fp)
        size = statinfo.st_size

        algos = {
            'Files': 'md5',
            'Checksums-Sha1': 'sha1',
            'Checksums-Sha256': 'sha256',
        }

        for key, algo in algos.items():
            if key not in self:
                self[key] = []

            m = hashlib.new(algo)
            with open(fp, 'rb') as fd:
                for chunk in iter((lambda: fd.read(128 * m.block_size)), b''):
                    m.update(chunk)

            if key != 'Files':
                self[key].append({
                    algo: m.hexdigest(),
                    'size': size,
                    'name': fp
                })
            else:
                self[key].append({
                    'md5sum': m.hexdigest(),
                    'size': size,
                    'section': 'debile',
                    'priority': 'debile',
                    'name': fp
                })
