# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2013 Paul Tagliamonte <paultag@debian.org>
# Copyright (C) 2014      Jon Severinsson <jon@severinsson.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import hashlib

from debian.deb822 import Changes as Changes_
from debian.deb822 import _gpg_multivalued


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
                for chunk in iter((lambda fd=fd, m=m: fd.read(128 * m.block_size)), b''):
                    m.update(chunk)

            if key != 'Files':
                self[key].append({algo: m.hexdigest(), 'size': size, 'name': fp})
            else:
                self[key].append(
                    {'md5sum': m.hexdigest(), 'size': size, 'section': 'debile', 'priority': 'debile', 'name': fp}
                )
