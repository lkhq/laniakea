# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2013 Paul Tagliamonte <paultag@debian.org>
# Copyright (C) 2014      Jon Severinsson <jon@severinsson.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import re
import hashlib

from debian.deb822 import Changes as Changes_
from debian.deb822 import _gpg_multivalued

import laniakea.typing as T


class ParseDEB822Error(Exception):
    """Exception raised for errors in parsing DEB822 data."""


# Copy of debian.deb822.Dsc with Package-List: support added.
class Dsc(_gpg_multivalued):
    _multivalued_fields = {
        'package-list': ['name', 'type', 'section', 'priority'],
        'files': ['md5sum', 'size', 'name'],
        'checksums-sha1': ['sha1', 'size', 'name'],
        'checksums-sha256': ['sha256', 'size', 'name'],
    }


re_parse_maintainer = re.compile(r"^\s*(\S.*\S)\s*\<([^\>]+)\>")


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


def split_maintainer_field(maintainer: str) -> T.Tuple[str, str, str]:
    """Split a Maintainer or Changed-By field into its parts

    :param maintainer:
    :return: A tuple consisting of the RFC822 compatible version of the maintainer field,
             the maintainer name and the maintainer email.
    """

    # sanity check
    maintainer = maintainer.strip()
    if not maintainer:
        return '', '', ''

    if maintainer.find('<') == -1:
        email = maintainer
        name = ''
    elif maintainer[0] == '<' and maintainer[-1:] == '>':
        email = maintainer[1:-1]
        name = ''
    else:
        m = re_parse_maintainer.match(maintainer)
        if not m:
            raise ParseDEB822Error('Does not parse as a valid Maintainer field.')
        name = m.group(1)
        email = m.group(2)

    if name.find(',') != -1 or name.find('.') != -1:
        rfc822_maint = '%s (%s)' % (email, name)
    else:
        rfc822_maint = '%s <%s>' % (name, email)

    if '@' not in email:
        raise ParseDEB822Error('No @ found in email address part.')

    return rfc822_maint, name, email
