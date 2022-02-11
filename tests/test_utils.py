# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import pytest


def test_base64():
    from laniakea.utils import decode_base64, encode_base64

    # test encode
    assert encode_base64(b'') == ''
    assert encode_base64(b'\x00') == 'AA'
    assert encode_base64(b'\x00\x00') == 'AAA'
    assert encode_base64(b'\x00\x00\x00') == 'AAAA'

    # test decode
    assert decode_base64('') == b''
    assert decode_base64('AA') == b'\x00'
    assert decode_base64('AAA') == b'\x00\x00'
    assert decode_base64('AAAA') == b'\x00\x00\x00'
    with pytest.raises(Exception):
        decode_base64('A')

    # test encoding of urlunsafe chars
    assert encode_base64(b'\xff\xe6\x9a') == '/+aa'
    assert encode_base64(b'\xff\xe6\x9a', True) == '_-aa'

    # test decoding of urlunsafe chars
    assert decode_base64('/+aa') == b'\xff\xe6\x9a'
    assert decode_base64('_-aa') == b'\xff\xe6\x9a'


def test_loadsections(localconfig):
    from laniakea.db import get_archive_sections

    sections = get_archive_sections()
    assert len(sections) == 59
    assert sections[0]['name'] == 'admin'
    assert sections[-1]['name'] == 'zope'


def test_is_remote_url():
    from laniakea.utils import is_remote_url

    assert is_remote_url('http://test.com')
    assert is_remote_url('https://example.org')
    assert not is_remote_url('/srv/mirror')
    assert not is_remote_url('file:///srv/test')
