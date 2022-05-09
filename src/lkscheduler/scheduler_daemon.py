# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from laniakea import LocalConfig
from laniakea.logging import log
from lkscheduler.config import SchedulerConfig


def task_repository_publish():
    """Publish the archive repositories."""
    import subprocess

    conf = SchedulerConfig()
    log.info('Publishing all repositories')
    subprocess.run([conf.lk_archive_exe, 'publish'], stdin=subprocess.DEVNULL, start_new_session=True, check=True)


def task_rubicon_scan():
    """Make Rubicon look for new uploads."""
    import subprocess

    conf = SchedulerConfig()
    subprocess.run([conf.rubicon_exe], stdin=subprocess.DEVNULL, start_new_session=True, check=True)


class SchedulerDaemon:
    """
    Laniakea maintenance scheduler daemon.
    """

    def __init__(self):
        from laniakea.db import Base, Database

        self._lconf = LocalConfig()
        self._sconf = SchedulerConfig()
        self._jobs = {}

        db = Database()
        jobstore = SQLAlchemyJobStore(engine=db.engine, tablename='maintenance_jobs', metadata=Base.metadata)
        self._scheduler = AsyncIOScheduler(jobstores={'default': jobstore})

        intervals_min = self._sconf.intervals_min
        if intervals_min['rubicon'] is not None:
            job = self._scheduler.add_job(
                task_rubicon_scan,
                'interval',
                id='rubicon',
                name='Import data from new uploads',
                jitter=60,
                minutes=intervals_min['rubicon'],
                replace_existing=True,
            )
            self._jobs[job.id] = job

        if intervals_min['publish-repos'] is not None:
            job = self._scheduler.add_job(
                task_repository_publish,
                'interval',
                id='publish-repos',
                name='Publish all repository data',
                jitter=20,
                minutes=intervals_min['publish-repos'],
                replace_existing=True,
            )
            self._jobs[job.id] = job

    def run(self):
        self._scheduler.start()

        try:
            asyncio.get_event_loop().run_forever()
        except (KeyboardInterrupt, SystemExit):
            pass
