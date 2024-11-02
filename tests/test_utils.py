# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import tempfile
from pathlib import Path

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


def test_is_remote_url():
    from laniakea.utils import is_remote_url

    assert is_remote_url('http://test.com')
    assert is_remote_url('https://example.org')
    assert not is_remote_url('/srv/mirror')
    assert not is_remote_url('file:///srv/test')


def test_renameat2():
    import laniakea.utils.renameat2 as renameat2

    # test exchange
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        apple_path = tmp.joinpath("apple")
        with open(apple_path, "w") as apple_out:
            apple_out.write("apple")

        orange_path = tmp.joinpath("orange")
        with open(orange_path, "w") as apple_out:
            apple_out.write("orange")

        renameat2.exchange_paths(apple_path, orange_path)

        with open(apple_path) as apple_in:
            assert apple_in.read() == "orange"

        with open(orange_path) as orange_in:
            assert orange_in.read() == "apple"

    # test rename & replace
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        apple_path = tmp.joinpath("apple")
        with open(apple_path, "w") as apple_out:
            apple_out.write("apple")

        orange_path = tmp.joinpath("orange")
        with open(orange_path, "w") as apple_out:
            apple_out.write("orange")

        renameat2.rename(apple_path, orange_path, replace=True)

        assert not apple_path.exists()

        with open(orange_path) as orange_in:
            assert orange_in.read() == "apple"

    # test rename & no replace
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        apple_path = tmp.joinpath("apple")
        with open(apple_path, "w") as apple_out:
            apple_out.write("apple")

        orange_path = tmp.joinpath("orange")
        with open(orange_path, "w") as apple_out:
            apple_out.write("orange")

        with pytest.raises(OSError):
            renameat2.rename(apple_path, orange_path, replace=False)

        assert apple_path.exists()
        assert orange_path.exists()


def test_traceback_decrypt():
    from laniakea.utils import decrypt_traceback_string, format_encrypted_traceback
    from laniakea.utils.traceback import compact_traceback

    try:
        # Code that raises an exception
        1 / 0
    except Exception as e:
        orig_tb = compact_traceback(e)
        encrypted = format_encrypted_traceback(e)
        decrypted = decrypt_traceback_string(encrypted)
        assert "ZeroDivisionError" in decrypted
        assert orig_tb == decrypted
        assert encrypted != decrypted

        # test decryption with wrong key
        key = b"wrongkey"
        with pytest.raises(Exception):
            decrypt_traceback_string(encrypted, key=key)
