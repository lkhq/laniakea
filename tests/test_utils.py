# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Matthias Klumpp <matthias@tenstral.net>
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

import pytest


def test_base64():
    from laniakea.utils import encode_base64, decode_base64

    # test encode
    assert encode_base64(b'') == u''
    assert encode_base64(b'\x00') == u'AA'
    assert encode_base64(b'\x00\x00') == u'AAA'
    assert encode_base64(b'\x00\x00\x00') == u'AAAA'

    # test decode
    assert decode_base64(u'') == b''
    assert decode_base64(u'AA') == b'\x00'
    assert decode_base64(u'AAA') == b'\x00\x00'
    assert decode_base64(u'AAAA') == b'\x00\x00\x00'
    with pytest.raises(Exception):
        decode_base64(u'A')

    # test encoding of urlunsafe chars
    assert encode_base64(b'\xff\xe6\x9a') == u'/+aa'
    assert encode_base64(b'\xff\xe6\x9a', True) == u'_-aa'

    # test decoding of urlunsafe chars
    assert decode_base64(u'/+aa') == b'\xff\xe6\x9a'
    assert decode_base64(u'_-aa') == b'\xff\xe6\x9a'


def test_loadsections(localconfig):
    from laniakea.db import get_archive_sections

    sections = get_archive_sections()
    assert len(sections) == 59
    assert sections[0]['name'] == 'admin'
    assert sections[-1]['name'] == 'zope'
