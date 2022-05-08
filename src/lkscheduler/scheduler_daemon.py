# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from laniakea import LocalConfig


def tick():
    print('The time is: %s' % datetime.now())


class SchedulerDaemon:
    '''
    Laniakea maintenance scheduler daemon.
    '''

    def __init__(self):
        from laniakea.db import Base, Database

        self._lconf = LocalConfig()

        db = Database()
        jobstore = SQLAlchemyJobStore(engine=db.engine, tablename='maintenance_jobs', metadata=Base.metadata)
        self._scheduler = AsyncIOScheduler(jobstores={'default': jobstore})
        self._scheduler.add_job(tick, 'interval', seconds=3, id='test-timed', name='Just a test')

    def run(self):
        self._scheduler.start()

        try:
            asyncio.get_event_loop().run_forever()
        except (KeyboardInterrupt, SystemExit):
            pass
