# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import asyncio
import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from laniakea import LocalConfig
from laniakea.logging import log
from lkscheduler.config import SchedulerConfig

scheduler_log = log.getLogger('scheduler')  # special logger to log package archive changes


def task_repository_publish():
    """Publish the archive repositories."""
    import subprocess

    conf = SchedulerConfig()
    log.info('Publishing all repositories')
    proc = subprocess.run(
        [conf.lk_archive_exe, 'publish'],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        check=False,
    )
    if proc.returncode == 0:
        scheduler_log.info('Archive-Publish: Success.')
    else:
        scheduler_log.error('Archive-Publish: Error: %s', str(proc.stdout, 'utf-8'))


def task_rubicon_scan():
    """Make Rubicon look for new uploads."""
    import subprocess

    conf = SchedulerConfig()
    proc = subprocess.run(
        [conf.rubicon_exe],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        check=False,
    )
    if proc.returncode == 0:
        scheduler_log.info('Rubicon: Success.')
    else:
        scheduler_log.error('Rubicon: Error: %s', str(proc.stdout, 'utf-8'))


def task_configure_rotate_logfile():
    """Configure the logger and set the right persistent log file."""
    lconf = LocalConfig()

    scheduler_log.setLevel(log.INFO)

    date_today = datetime.date.today()
    archive_log_dir = os.path.join(lconf.log_root_dir, 'scheduler', date_today.strftime("%Y"))
    os.makedirs(archive_log_dir, exist_ok=True)

    fh = log.FileHandler(os.path.join(archive_log_dir, 'scheduler-w{}.log'.format(date_today.isocalendar().week)))
    formatter = log.Formatter('%(levelname).1s: %(asctime)s: %(message)s', datefmt='%Y-%d-%m %H:%M:%S')
    fh.setFormatter(formatter)
    scheduler_log.handlers.clear()
    scheduler_log.addHandler(fh)


class SchedulerDaemon:
    """
    Laniakea maintenance scheduler daemon.
    """

    def __init__(self):
        import systemd.daemon

        from laniakea.db import Base, Database

        self._lconf = LocalConfig()
        self._sconf = SchedulerConfig()
        self._jobs = {}

        # configure logging
        task_configure_rotate_logfile()

        db = Database()
        jobstore = SQLAlchemyJobStore(engine=db.engine, tablename='maintenance_jobs', metadata=Base.metadata)
        self._scheduler = AsyncIOScheduler(jobstores={'default': jobstore})

        # we're ready now
        systemd.daemon.notify('READY=1')

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

        # internal maintenance tasks
        job = self._scheduler.add_job(
            task_configure_rotate_logfile,
            'interval',
            id='internal-log-rotate',
            name='Rotate scheduler logs',
            jitter=60,
            minutes=60,
            replace_existing=True,
        )

    def run(self):
        self._scheduler.start()

        try:
            asyncio.get_event_loop().run_forever()
        except (KeyboardInterrupt, SystemExit):
            pass
