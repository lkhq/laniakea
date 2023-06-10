# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import re
from datetime import datetime

import humanize
from sqlalchemy import func

import laniakea.typing as T
from laniakea.db import StatsEntry

UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def is_uuid(value):
    '''
    Quickly check if :value is a UUID.
    '''
    return True if UUID_RE.match(value) else False


def humanized_timediff(time):
    '''
    Get a time difference of :time with the current clock time
    in a human-readable format.
    '''
    if not time:
        return 'Never'

    timediff = datetime.utcnow().replace(microsecond=0) - time
    return humanize.naturaltime(timediff)


def fetch_statistics_for(session, stat_key: str, start_at: datetime) -> list[dict[str, T.Any]] | None:
    values = (
        session.query(func.extract('epoch', StatsEntry.time), StatsEntry.value)
        .filter(StatsEntry.key == stat_key, StatsEntry.time > start_at)
        .order_by(StatsEntry.time)
        .all()
    )
    if not values:
        return None
    return [{'x': int(v[0]), 'y': v[1]} for v in values]
