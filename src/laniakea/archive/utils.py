# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
from typing import Dict

from laniakea.db import (
    ArchiveFile,
    PackageInfo,
    debtype_from_string,
    packagepriority_from_string,
)
from laniakea.utils import split_strip


def checksums_list_to_file(cslist, checksum: str, files=None, *, base_dir=None) -> Dict[str, ArchiveFile]:
    """Convert a list of checkums (from a Sources, Packages or .dsc file) to ArchiveFile objects."""

    if not files:
        files = {}
    if not cslist:
        return files
    for fdata in cslist:
        basename = os.path.basename(fdata['name'])

        af = files.get(basename)
        if not af:
            af = ArchiveFile()
        if checksum == 'md5':
            af.md5sum = fdata['md5sum']
        else:
            setattr(af, checksum + 'sum', fdata[checksum])
        af.size = fdata['size']

        if not base_dir:
            af.fname = basename
        else:
            af.fname = os.path.join(base_dir, basename)
        files[basename] = af

    return files


def parse_package_list_str(pkg_list_raw, default_version=None):
    '''
    Parse a "Package-List" field and return its information in
    PackageInfo data structures.
    See https://www.debian.org/doc/debian-policy/ch-controlfields.html#package-list
    '''

    res = []

    for line in pkg_list_raw.split('\n'):
        parts = split_strip(line, ' ')
        if len(parts) < 4:
            continue

        pi = PackageInfo()
        pi.name = parts[0]
        pi.version = default_version
        pi.deb_type = debtype_from_string(parts[1])
        pi.section = parts[2]
        pi.priority = packagepriority_from_string(parts[3])

        if len(parts) > 4:
            # we have additional data
            raw_vals = split_strip(parts[4], ' ')
            for v in raw_vals:
                if v.startswith('arch='):
                    # handle architectures
                    pi.architectures = v[5:].split(',')

        res.append(pi)
    return res
