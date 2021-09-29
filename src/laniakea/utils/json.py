# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import json


def json_compact_dump(obj, as_bytes=False):
    '''
    Convert :obj to JSON string reproducibly and
    in the most compact form possible.
    '''
    s = json.dumps(obj,
                   ensure_ascii=False,
                   separators=(',', ':'),
                   sort_keys=True)
    if as_bytes:
        return bytes(s, 'utf-8')
    return s
