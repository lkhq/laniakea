# -*- coding: utf-8 -*-
#
# Copyright (C) 2023-2024 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+


import os
import base64
import hashlib
import platform
import traceback

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, modes, algorithms

from laniakea.logging import log


def create_obfuscation_key():
    """Generate a 256-bit AES key from the machine ID."""

    try:
        with open('/etc/machine-id', 'r') as f:
            machine_id = f.read().strip()
    except FileNotFoundError:
        log.warning('Machine ID not found, using a fallback value.')
        machine_id = platform.node()

    key_seed = 'laniakea-' + machine_id
    return hashlib.sha256(key_seed.encode()).digest()


def compact_traceback(exc):
    """Generate a more compacted traceback string."""

    tb_list = traceback.format_exception(type(exc), exc, exc.__traceback__)
    compacted_tb = ''.join(line for line in tb_list if not line.startswith("Traceback (most recent call last):"))
    return compacted_tb.strip()


def format_encrypted_traceback(exc, *, key: bytes | None = None):
    """Format a traceback string and lightly encrypt it for public logging.
    :param exc: The exception to format
    """

    # generate a compacted traceback string
    tb_str = compact_traceback(exc)

    if not key:
        key = create_obfuscation_key()

    # pad the data to align with AES block size
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(tb_str.encode('utf-8')) + padder.finalize()

    # encrypt with AES-CBC
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encrypted_tb = cipher.encryptor().update(padded_data) + cipher.encryptor().finalize()

    # concatenate IV and encrypted data for encoding
    encrypted_payload = iv + encrypted_tb

    # encode as base85
    return base64.b85encode(encrypted_payload).decode('utf-8')


def decrypt_traceback_string(encoded_traceback: str, *, key: bytes | None = None):
    """Decrypt an encrypted traceback string with the encryption key of the current machine."""

    if not key:
        key = create_obfuscation_key()

    # decode from base85
    encrypted_payload = base64.b85decode(encoded_traceback)

    # extract the IV and encrypted data
    iv = encrypted_payload[:16]
    encrypted_tb = encrypted_payload[16:]

    # decrypt using AES-CBC
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    padded_data = cipher.decryptor().update(encrypted_tb) + cipher.decryptor().finalize()

    # remove padding and return the original traceback
    unpadder = padding.PKCS7(128).unpadder()
    tb_str = unpadder.update(padded_data) + unpadder.finalize()

    return tb_str.decode('utf-8')
