# -*- coding: utf-8 -*-
#
# Copyright (C) 2019-2021 Matthias Klumpp <matthias@tenstral.net>
# Copyright (C) 2014-2015 OpenMarket Ltd
#
# SPDX-License-Identifier: LGPL-3.0+ AND Apache-2.0

import nacl.signing
import pytest

from laniakea.msgstream.signedjson import (SignatureVerifyException, sign_json,
                                           signature_ids, verify_signed_json)
from laniakea.msgstream.signing import (decode_signing_key_base64,
                                        decode_verify_key_bytes,
                                        encode_signing_key_base64,
                                        encode_verify_key_base64,
                                        generate_signing_key, get_verify_key,
                                        is_signing_algorithm_supported,
                                        read_old_signing_keys,
                                        read_signing_keys, write_signing_keys)
from laniakea.utils import decode_base64, encode_base64


class TestGenerate:
    def test_generate_key(self):
        my_version = "my_version"
        my_key = generate_signing_key(my_version)
        assert my_key.alg == "ed25519"
        assert my_key.version == my_version


class TestDecode:
    def setup_method(self, test_method):
        self.version = "my_version"
        self.key = generate_signing_key(self.version)
        self.key_base64 = encode_signing_key_base64(self.key)
        self.verify_key = get_verify_key(self.key)
        self.verify_key_base64 = encode_verify_key_base64(self.verify_key)

    def test_decode(self):
        decoded_key = decode_signing_key_base64(
            "ed25519", self.key_base64, self.version
        )
        assert decoded_key.alg == "ed25519"
        assert decoded_key.version == self.version

    def test_decode_invalid_base64(self):
        with pytest.raises(Exception):
            decode_signing_key_base64("ed25519", "not base 64", self.version)

    def test_decode_signing_invalid_algorithm(self):
        with pytest.raises(Exception):
            decode_signing_key_base64("not a valid alg", "", self.version)

    def test_decode_invalid_key(self):
        with pytest.raises(Exception):
            decode_signing_key_base64("ed25519", "", self.version)

    def test_read_keys(self):
        stream = ["ed25519 %s %s" % (self.version, self.key_base64)]
        keys = read_signing_keys(stream)
        assert len(keys) == 1

    def test_read_old_keys(self):
        stream = ["ed25519 %s 0 %s" % (self.version, self.verify_key_base64)]
        keys = read_old_signing_keys(stream)
        assert len(keys) == 1

    def test_decode_verify_invalid_algorithm(self):
        with pytest.raises(Exception):
            decode_verify_key_bytes("not a valid alg", self.verify_key)

    def test_write_signing_keys(self):
        class MockStream:
            def write(self, data):
                pass
        write_signing_keys(MockStream(), [self.key])


class TestAlgorithmSupported:
    def test_ed25519(self):
        assert is_signing_algorithm_supported("ed25519:an_id")

    def test_unsupported(self):
        assert not is_signing_algorithm_supported("unsupported:")


SIGNING_KEY_SEED = decode_base64(
    "YJDBA9Xnr2sVqXD9Vj7XVUnmFZcZrlw8Md7kMW+3XA1"
)

KEY_ALG = "ed25519"
KEY_VER = 1
KEY_NAME = "%s:%d" % (KEY_ALG, KEY_VER)


class TestKnownKey:
    '''
    An entirely deterministic test using a given signing key seed, so that
    other implementations can compare that they get the same result.
    '''

    def setup_method(self, test_method):
        self.signing_key = nacl.signing.SigningKey(SIGNING_KEY_SEED)
        self.signing_key.alg = KEY_ALG
        self.signing_key.version = KEY_VER

    def test_sign_minimal(self):
        res = {
            'signatures': {
                'domain': {
                    KEY_NAME: "K8280/U9SSy9IVtjBuVeLr+HpOB4BQFWbg+UZaADMt"
                              "TdGYI7Geitb76LTrr5QV/7Xg4ahLwYGYZzuHGZKM5ZAQ"
                },
            }
        }
        assert sign_json({}, "domain", self.signing_key) == res

    def test_sign_with_data(self):
        res = {
            'one': 1,
            'two': "Two",
            'signatures': {
                'domain': {
                    KEY_NAME: "KqmLSbO39/Bzb0QIYE82zqLwsA+PDzYIpIRA2sRQ4s"
                              "L53+sN6/fpNSoqE7BP7vBZhG6kYdD13EIMJpvhJI+6Bw"
                },
            }
        }
        assert sign_json({'one': 1, 'two': "Two"}, "domain", self.signing_key) == res


class MockSigningKey:
    alg = "mock"
    version = "test"

    def sign(self, signed_bytes):
        self.signed_bytes = signed_bytes
        return MockSignature()


class MockVerifyKey:
    alg = "mock"
    version = "test"

    def verify(self, message, sig):
        if not sig == b"x_______":
            raise Exception()


class MockSignature:
    def __init__(self):
        self.signature = b"x_______"


class TestJsonSign:
    def setup_method(self, test_method):
        self.message = {'foo': 'bar', 'unsigned': {}}
        self.sigkey = MockSigningKey()
        assert self.sigkey.alg == 'mock'
        self.signed = sign_json(self.message, 'Alice', self.sigkey)
        self.verkey = MockVerifyKey()

    def test_sign_and_verify(self):
        assert 'signatures' in self.signed
        assert 'Alice' in self.signed['signatures']
        assert 'mock:test' in self.signed['signatures']['Alice']
        assert self.signed['signatures']['Alice']['mock:test'] == encode_base64(b'x_______')

        assert self.sigkey.signed_bytes == b'{"foo":"bar"}'
        verify_signed_json(self.signed, 'Alice', self.verkey)

    def test_signature_ids(self):
        key_ids = signature_ids(
            self.signed, 'Alice', supported_algorithms=['mock']
        )
        assert key_ids == ['mock:test']

    def test_verify_fail(self):
        self.signed['signatures']['Alice']['mock:test'] = encode_base64(
            b'not a signature'
        )
        with pytest.raises(SignatureVerifyException):
            verify_signed_json(self.signed, 'Alice', self.verkey)

    def test_verify_fail_no_signatures(self):
        with pytest.raises(SignatureVerifyException):
            verify_signed_json({}, 'Alice', self.verkey)

    def test_verify_fail_no_signature_for_alice(self):
        with pytest.raises(SignatureVerifyException):
            verify_signed_json({'signatures': {}}, 'Alice', self.verkey)

    def test_verify_fail_not_base64(self):
        invalid = {'signatures': {'Alice': {'mock:test': 'not base64'}}}
        with pytest.raises(SignatureVerifyException):
            verify_signed_json(invalid, 'Alice', self.verkey)
