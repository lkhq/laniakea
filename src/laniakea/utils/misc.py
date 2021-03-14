# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2019 Matthias Klumpp <matthias@tenstral.net>
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

import os
import re
import requests
from contextlib import contextmanager


def get_dir_shorthand_for_uuid(uuid):
    '''
    Get short prefix for UUIDs for use in directory names.
    '''
    s = str(uuid)

    if len(s) > 2:
        return s[0:2]
    return None


def random_string(length=8):
    '''
    Generate a random alphanumerical string with length :length.
    '''
    import random
    import string

    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(length)])


@contextmanager
def cd(where):
    ncwd = os.getcwd()
    try:
        yield os.chdir(where)
    finally:
        os.chdir(ncwd)


def listify(item):
    '''
    Return a list of :item, unless :item already is a lit.
    '''
    if not item:
        return []
    return item if type(item) == list else [item]


def stringify(item):
    '''
    Convert anything into a string, if it isn't one already.
    Assume UTF-8 encoding if we have bytes.
    '''
    if type(item) is str:
        return item
    if type(item) is bytes:
        return str(item, 'utf-8')

    return str(item)


def is_remote_url(uri):
    ''' Check if string contains a remote URI. '''

    uriregex = re.compile('^(https?|ftps?)://')
    return uriregex.match(uri) is not None


def download_file(url, fname, check=False, headers: dict = None, **kwargs):

    if not headers:
        headers = {}

    hdr = {'user-agent': 'laniakea/0.0.1'}
    hdr.update(headers)

    r = requests.get(url, stream=True, headers=hdr, **kwargs)
    if r.status_code == 200:
        with open(fname, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                f.write(chunk)
        return r.status_code

    if check:
        raise Exception('Unable to download file "{}". Status: {}'.format(url, r.status_code))
    return r.status_code


@contextmanager
def open_compressed(fname, mode='rb'):
    '''
    Open a few compressed filetypes easily.
    '''

    lower_fname = fname.lower()
    f = None
    if lower_fname.endswith('.xz'):
        import lzma
        f = lzma.open(fname, mode=mode)
    elif lower_fname.endswith('.gz'):
        import gzip
        f = gzip.open(fname, mode=mode)
    else:
        raise Exception('Can not decompress file (compression type not recognized): {}'.format(fname))

    try:
        yield f
    finally:
        f.close()


def split_strip(s, sep):
    ''' Split a string, removing empty segments from the result and stripping the individual parts '''
    res = []
    for part in s.split(sep):
        if part:
            res.append(part.strip())
    return res
