# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Matthias Klumpp <matthias@tenstral.net>
# Copyright (c) 2014 OpenMarket Ltd
#
# SPDX-License-Identifier: LGPL-3.0+ AND Apache-2.0

import nacl.signing
from laniakea.utils import encode_base64, decode_base64

NACL_ED25519 = 'ed25519'
SUPPORTED_ALGORITHMS = [NACL_ED25519]


def generate_signing_key(version=0):
    '''
    Generate a new signing key
    Args:
        version (str): Identifies this key out the keys for this entity.
    Returns:
        A SigningKey object.
    '''
    key = nacl.signing.SigningKey.generate()
    key.version = version
    key.alg = NACL_ED25519
    return key


def get_verify_key(signing_key):
    '''Get a verify key from a signing key'''
    verify_key = signing_key.verify_key
    verify_key.version = signing_key.version
    verify_key.alg = signing_key.alg
    return verify_key


def decode_signing_key_base64(algorithm, key_base64, version=0):
    '''
    Decode a base64 encoded signing key
    Args:
        algorithm (str): The algorithm the key is for (currently 'ed25519').
        version (str): Identifies this key out of the keys for this entity.
        key_base64 (str): Base64 encoded bytes of the key.
    Returns:
        A SigningKey object.
    '''
    if algorithm == NACL_ED25519:
        key_bytes = decode_base64(key_base64)
        key = nacl.signing.SigningKey(key_bytes)
        key.version = version
        key.alg = NACL_ED25519
        return key
    else:
        raise ValueError('Unsupported algorithm {}'.format(algorithm,))


def encode_signing_key_base64(key):
    '''
    Encode a signing key as base64
    Args:
        key (SigningKey): A signing key to encode.
    Returns:
        base64 encoded string.
    '''
    return encode_base64(key.encode())


def encode_verify_key_base64(key):
    '''
    Encode a verify key as base64
    Args:
        key (VerifyKey): A signing key to encode.
    Returns:
        base64 encoded string.
    '''
    return encode_base64(key.encode())


def is_signing_algorithm_supported(key_id):
    '''Is the signing algorithm for this key_id supported'''
    if key_id.startswith(NACL_ED25519 + ':'):
        return True
    else:
        return False


def decode_verify_key_bytes(key_id, key_bytes):
    '''
    Decode a raw verify key
    Args:
        key_id (str): Identifies this key out of the keys for this entity.
        key_bytes (str): Raw bytes of the key.
    Returns:
        A VerifyKey object.
    '''
    if key_id.startswith(NACL_ED25519 + ':'):
        version = key_id[len(NACL_ED25519) + 1:]
        key = nacl.signing.VerifyKey(key_bytes)
        key.version = version
        key.alg = NACL_ED25519
        return key
    else:
        raise ValueError('Unsupported algorithm {}'.format(key_id))


def read_signing_keys(stream):
    '''
    Reads a list of keys from a stream
    Args:
        stream : A stream to iterate for keys.
    Returns:
        list of SigningKey objects.
    '''
    keys = []
    for line in stream:
        algorithm, version, key_base64 = line.split()
        key = decode_signing_key_base64(algorithm, key_base64, version)
        keys.append(key)
    return keys


def read_old_signing_keys(stream):
    '''
    Reads a list of old keys from a stream
    Args:
        stream : A stream to iterate for keys.
    Returns:
        list of VerifyKey objects.
    '''
    keys = []
    for line in stream:
        algorithm, version, expired, key_base64 = line.split()
        key_name = '%s:%s' % (algorithm, version,)
        key = decode_verify_key_bytes(key_name, decode_base64(key_base64))
        key.expired = int(expired)
        keys.append(key)
    return keys


def write_signing_keys(stream, keys):
    '''
    Writes a list of keys to a stream.
    Args:
        stream: Stream to write keys to.
        keys: List of SigningKey objects.
    '''
    for key in keys:
        key_base64 = encode_signing_key_base64(key)
        stream.write('{} {} {}\n'.format(key.alg, key.version, key_base64))


def keyfile_read_verify_key(fname):
    '''
    Read verify key and signer ID from a Laniakea keyfile and return them
    as tuple.
    The resulting key can be used to verify messages.
    '''
    signer_id = None
    verify_key = None

    with open(fname, 'r') as f:
        metadata_sec = False
        ed_sec = False
        for line in f:
            if not line.startswith(' '):
                ed_sec = False
                metadata_sec = False
            line = line.strip()
            if line == 'metadata':
                metadata_sec = True
                continue
            if line == 'ed':
                ed_sec = True
                continue

            if metadata_sec:
                if line.startswith('id'):
                    key, value = line.split('=')
                    signer_id = value.strip().strip('"')
                    continue
            elif ed_sec:
                if line.startswith('verify-key'):
                    key, value = line.split('=')
                    verify_key = value.strip().strip('"')
                    continue

    if verify_key:
        verify_key = decode_verify_key_bytes(NACL_ED25519 + ':' + '0',
                                             decode_base64(verify_key))

    return signer_id, verify_key


def keyfile_read_signing_key(fname):
    '''
    Read signing key and signer ID from a Laniakea keyfile and return them
    as tuple.
    The resulting key can be used to sign new messages.
    '''
    signer_id = None
    signing_key = None

    with open(fname, 'r') as f:
        metadata_sec = False
        ed_sec = False
        for line in f:
            if not line.startswith(' '):
                ed_sec = False
                metadata_sec = False
            line = line.strip()
            if line == 'metadata':
                metadata_sec = True
                continue
            if line == 'ed':
                ed_sec = True
                continue

            if metadata_sec:
                if line.startswith('id'):
                    key, value = line.split('=')
                    signer_id = value.strip().strip('"')
                    continue
            elif ed_sec:
                if line.startswith('signing-key'):
                    key, value = line.split('=')
                    signing_key = value.strip().strip('"')
                    continue

    if signing_key:
        signing_key = decode_signing_key_base64(NACL_ED25519, signing_key, 0)

    return signer_id, signing_key
