# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import asyncio
import datetime
from contextlib import contextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from laniakea import LocalConfig
from laniakea.utils import process_file_lock
from laniakea.logging import log
from lkscheduler.config import SchedulerConfig

scheduler_log = log.getLogger('scheduler')  # special logger to log package archive changes


class JobsRegistry:
    """Helper class storing registered job details and locks."""

    def __init__(self):
        self.jobs = {}

    def set_job(self, job):
        self.jobs[job.id] = job

    @contextmanager
    def lock_publish_job(self):
        """Prevent publishing from being run simultaneously."""
        with process_file_lock('scheduler_publish-repos'):
            yield


def task_repository_publish(registry: JobsRegistry):
    """Publish the archive repositories."""
    import subprocess

    with registry.lock_publish_job():
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


def task_repository_expire(registry: JobsRegistry):
    """Expire old packages in all repositories."""
    import subprocess

    with registry.lock_publish_job():
        conf = SchedulerConfig()
        log.info('Cleaning up repository data')
        proc = subprocess.run(
            [conf.lk_archive_exe, 'expire'],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            check=False,
        )
    if proc.returncode == 0:
        scheduler_log.info('Archive-Expire: Success.')
    else:
        scheduler_log.error('Archive-Expire: Error: %s', str(proc.stdout, 'utf-8'))


def task_rubicon_scan(registry: JobsRegistry):
    """Make Rubicon look for new uploads."""
    import subprocess

    with registry.lock_publish_job():
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


def task_spears_migrate(registry: JobsRegistry):
    """Make Spears migrate packages."""
    import subprocess

    with registry.lock_publish_job():
        conf = SchedulerConfig()

        # update static data
        proc = subprocess.run(
            [conf.spears_exe, 'update'],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            check=False,
        )
        if proc.returncode != 0:
            scheduler_log.error('Spears-Update: Error: %s', str(proc.stdout, 'utf-8'))
            return

        # run the actual migration
        proc = subprocess.run(
            [conf.spears_exe, 'migrate'],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            check=False,
        )
    if proc.returncode == 0:
        scheduler_log.info('Spears: Success.')
    else:
        scheduler_log.error('Spears: Error: %s', str(proc.stdout, 'utf-8'))


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

        from laniakea.db import Base, Database, session_scope

        self._lconf = LocalConfig()
        self._sconf = SchedulerConfig()
        self._registry = JobsRegistry()

        # configure logging
        task_configure_rotate_logfile()

        db = Database()
        jobstore = SQLAlchemyJobStore(engine=db.engine, tablename='maintenance_jobs', metadata=Base.metadata)
        self._scheduler = AsyncIOScheduler(jobstores={'default': jobstore})

        # we're ready now
        self._scheduler.start()
        systemd.daemon.notify('READY=1')

        intervals_min = self._sconf.intervals_min
        if intervals_min['rubicon'] is not None:
            job = self._scheduler.add_job(
                task_rubicon_scan,
                'interval',
                args=(self._registry,),
                id='rubicon',
                name='Import data from new uploads',
                jitter=60,
                minutes=intervals_min['rubicon'],
                max_instances=1,
                replace_existing=True,
            )
            self._registry.set_job(job)

        if intervals_min['publish-repos'] is not None:
            job = self._scheduler.add_job(
                task_repository_publish,
                'interval',
                args=(self._registry,),
                id='publish-repos',
                name='Publish all repository data',
                jitter=20,
                minutes=intervals_min['publish-repos'],
                max_instances=1,
                replace_existing=True,
            )
            self._registry.set_job(job)

        if intervals_min['expire-repos'] is not None:
            job = self._scheduler.add_job(
                task_repository_expire,
                'interval',
                args=(self._registry,),
                id='expire-repos',
                name='Expire old repository data',
                jitter=2 * 60,
                minutes=intervals_min['expire-repos'],
                max_instances=1,
                replace_existing=True,
            )
            self._registry.set_job(job)

        if intervals_min['spears-migrate'] is not None:
            from laniakea.db.spears import SpearsMigrationTask

            with session_scope() as session:
                mtask_ids = session.query(SpearsMigrationTask.id).all()
                if mtask_ids:
                    job = self._scheduler.add_job(
                        task_spears_migrate,
                        'interval',
                        args=(self._registry,),
                        id='spears-migrate',
                        name='Migrate packages between suites.',
                        jitter=20,
                        minutes=intervals_min['spears-migrate'],
                        max_instances=1,
                        replace_existing=True,
                    )
                    self._registry.set_job(job)
                else:
                    log.info('Not creating Spears migration job: No migration tasks configured.')

        # internal maintenance tasks
        self._scheduler.add_job(
            task_configure_rotate_logfile,
            'interval',
            id='internal-log-rotate',
            name='Rotate scheduler logs',
            jitter=60,
            minutes=60,
            max_instances=1,
            replace_existing=True,
        )

    def run(self):
        try:
            asyncio.get_event_loop().run_forever()
        except (KeyboardInterrupt, SystemExit):
            pass
