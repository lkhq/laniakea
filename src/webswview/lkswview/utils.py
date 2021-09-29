# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import re
import humanize
from datetime import datetime


UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def is_uuid(value):
    '''
    Quickly check if :value is a UUID.
    '''
    return True if UUID_RE.match(value) else False


def humanized_timediff(time):
    '''
    Get a time difference of _time with the current clock time
    in a human-readable format.
    '''
    if not time:
        return 'Never'

    timediff = datetime.utcnow().replace(microsecond=0) - time
    return humanize.naturaltime(timediff)
