# -*- coding: utf-8 -*-
#
# Copyright (C) 2019-2022 Matthias Klumpp <matthias@tenstral.net>
# Copyright (C) 2014-2015 OpenMarket Ltd
#
# SPDX-License-Identifier: LGPL-3.0+ AND Apache-2.0

import base64


def encode_base64(input_bytes, urlsafe=False):
    '''
    Encode bytes as a base64 string without any padding.
    '''

    encode = base64.urlsafe_b64encode if urlsafe else base64.b64encode
    output_bytes = encode(input_bytes)
    output_string = output_bytes.decode('ascii')
    return output_string.rstrip('=')


def decode_base64(input_string):
    '''
    Decode a base64 string to bytes inferring padding from the length of the
    string.
    '''

    input_bytes = input_string.encode('ascii')
    input_len = len(input_bytes)
    padding = b'=' * (3 - ((input_len + 3) % 4))
    decode = base64.b64decode
    if '-' in input_string or '_' in input_string:
        decode = base64.urlsafe_b64decode
    output_bytes = decode(input_bytes + padding)
    return output_bytes
