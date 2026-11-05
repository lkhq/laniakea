# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import asyncio
import datetime
import subprocess
from contextlib import contextmanager

from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from laniakea import LkModule, LocalConfig
from laniakea.utils import process_file_lock
from laniakea.logging import log
from laniakea.msgstream import EventEmitter
from lkscheduler.config import SchedulerConfig
from lkscheduler.statscollector import task_collect_statistics

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
        with process_file_lock('scheduler_publish-repos', wait=True):
            yield


class TaskError(Exception):
    """A scheduled task did not complete successfully."""


def run_task_tool(title: str, cmd: list[str]) -> str | None:
    """Run a Laniakea tool as part of a scheduled task.

    The complete output of a failed run is written to the scheduler log.

    :param title: Name of this task step, used as prefix for log messages.
    :param cmd: The command to run.
    :return: A short error summary if the command failed, None on success.
    """

    # Our tools are written in Python, which buffers stdout when it is not a TTY. That would mix up
    # the order of stdout and stderr lines in the output we log, so we disable output buffering.
    tool_env = dict(os.environ)
    tool_env['PYTHONUNBUFFERED'] = '1'

    proc = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=tool_env,
        start_new_session=True,
        check=False,
    )
    if proc.returncode == 0:
        return None

    output = str(proc.stdout, 'utf-8', errors='replace')
    scheduler_log.error('%s: Error: %s', title, output)

    # the last line usually holds the actual error message, e.g. the one of an exception
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return '{} failed with exit code {}: {}'.format(title, proc.returncode, lines[-1] if lines else 'No output.')


def task_repository_publish(registry: JobsRegistry):
    """Publish the archive repositories."""

    with registry.lock_publish_job():
        conf = SchedulerConfig()
        log.info('Publishing all repositories')
        error = run_task_tool('Archive-Publish', [conf.lk_archive_exe, 'publish'])
    if error:
        raise TaskError(error)
    scheduler_log.info('Archive-Publish: Success.')


def task_repository_expire(registry: JobsRegistry):
    """Expire old packages and data in all repositories."""

    errors = []

    # expire packages
    with registry.lock_publish_job():
        conf = SchedulerConfig()
        log.info('Cleaning up repository data')
        error = run_task_tool('Archive-Expire', [conf.lk_archive_exe, 'expire'])
        if error:
            errors.append(error)
        else:
            scheduler_log.info('Archive-Expire: Success.')

    # remove job data that is no longer needed, even if expiring packages has failed
    with registry.lock_publish_job():
        log.info('Cleaning up job data')
        error = run_task_tool('Archive-JobCleanup', [conf.lk_archive_exe, 'cleanup-jobs'])
        if error:
            errors.append(error)
        else:
            scheduler_log.info('Archive-JobCleanup: Success.')

    if errors:
        raise TaskError('\n'.join(errors))


def task_rubicon_scan(registry: JobsRegistry):
    """Make Rubicon look for new uploads."""

    with registry.lock_publish_job():
        conf = SchedulerConfig()
        error = run_task_tool('Rubicon', [conf.rubicon_exe])
    if error:
        raise TaskError(error)
    scheduler_log.info('Rubicon: Success.')


def task_spears_migrate(registry: JobsRegistry):
    """Make Spears migrate packages."""

    with registry.lock_publish_job():
        conf = SchedulerConfig()

        # update static data
        error = run_task_tool('Spears-Update', [conf.spears_exe, 'update'])
        if error:
            raise TaskError(error)

        # run the actual migration
        error = run_task_tool('Spears', [conf.spears_exe, 'migrate'])
    if error:
        raise TaskError(error)
    scheduler_log.info('Spears: Success.')


def task_debcheck(registry: JobsRegistry):
    """Make Debcheck test dependencies."""

    errors = []
    with registry.lock_publish_job():
        conf = SchedulerConfig()

        # check sources
        error = run_task_tool('Debcheck sources check', [conf.debcheck_exe, 'sources'])
        if error:
            errors.append(error)

        # check binaries, even if checking sources has failed
        error = run_task_tool('Debcheck binaries check', [conf.debcheck_exe, 'binaries'])
        if error:
            errors.append(error)

    if errors:
        raise TaskError('\n'.join(errors))
    scheduler_log.info('Debcheck: Success.')


def task_ariadne_update(registry: JobsRegistry):
    """Make Ariadne verify & update all package autobuild data."""

    with registry.lock_publish_job():
        conf = SchedulerConfig()
        error = run_task_tool('Ariadne', [conf.lk_archive_exe, 'update-jobs'])
    if error:
        raise TaskError(error)
    scheduler_log.info('Ariadne: Success.')


def task_synchrotron_autosync(registry: JobsRegistry):
    """Run automatic package synchronization."""

    with registry.lock_publish_job():
        conf = SchedulerConfig()
        error = run_task_tool('Synchrotron Autosync', [conf.synchrotron_exe, 'autosync'])
    if error:
        raise TaskError(error)
    scheduler_log.info('Synchrotron Autosync: Success.')


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
        self._emitter = EventEmitter(LkModule.SCHEDULER)

        # configure logging
        task_configure_rotate_logfile()

        db = Database()
        self._jobstore = SQLAlchemyJobStore(engine=db.engine, tablename='maintenance_jobs', metadata=Base.metadata)
        self._scheduler = AsyncIOScheduler(jobstores={'default': self._jobstore})
        self._scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)

        # we're ready now
        self._scheduler.start()
        systemd.daemon.notify('READY=1')

        # get a list of all job IDs that we need to configure
        self._job_setup_todo = set()
        for job in self._jobstore.get_all_jobs():
            self._job_setup_todo.add(job.id)

        self._configure_job(task_collect_statistics, 'statistics', 'Collect statistical data', jitter=20)
        self._configure_job(task_rubicon_scan, 'rubicon', 'Import data from new uploads', jitter=60)
        self._configure_job(task_repository_publish, 'publish-repos', 'Publish all repository data', jitter=20)
        self._configure_job(task_repository_expire, 'expire-repos', 'Expire old repository data', jitter=2 * 60)
        self._configure_job(task_debcheck, 'debcheck', 'Check package dependencies', jitter=30)
        self._configure_job(task_ariadne_update, 'ariadne-update', 'Check package autobuild data', jitter=40)

        with session_scope() as session:
            from laniakea.db import SynchrotronConfig, SpearsMigrationTask

            # Spears
            migrate_job_id = 'spears-migrate'
            mtask_ids = session.query(SpearsMigrationTask.id).all()
            if mtask_ids:
                self._configure_job(task_spears_migrate, migrate_job_id, 'Migrate packages between suites', jitter=20)
            else:
                log.info('Not creating Spears migration job: No migration tasks configured.')
                job = self._jobstore.lookup_job(migrate_job_id)
                if job:
                    self._jobstore.remove_job(migrate_job_id)

            # Synchrotron
            autosync_job_id = 'synchrotron-autosync'
            sconf_ids = (
                session.query(SynchrotronConfig.id)
                .filter(
                    SynchrotronConfig.sync_enabled == True, SynchrotronConfig.sync_auto_enabled == True  # noqa: E712
                )
                .all()
            )
            if sconf_ids:
                self._configure_job(
                    task_synchrotron_autosync,
                    autosync_job_id,
                    'Automatically synchronize packages with an origin OS',
                    jitter=60,
                )
            else:
                log.info('Not creating Synchrotron autosync job: No autosync tasks configured.')
                job = self._jobstore.lookup_job(autosync_job_id)
                if job:
                    self._jobstore.remove_job(autosync_job_id)

        # internal maintenance tasks
        self._scheduler.add_job(
            task_configure_rotate_logfile,
            'interval',
            id='internal-log-rotate',
            name='Rotate scheduler logs',
            jitter=60,
            minutes=60,
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        self._job_setup_todo.discard('internal-log-rotate')

        # remove all jobs that we haven't configured and which are therefore stale
        for job_id in self._job_setup_todo:
            self._jobstore.remove_job(job_id)
        self._job_setup_todo = set()

    def _configure_job(self, func, job_id, job_name, *, jitter):
        """Add or update a job."""
        from apscheduler.util import undefined

        job = self._jobstore.lookup_job(job_id)
        intervals_min = self._sconf.intervals_min
        if intervals_min[job_id] is None:
            if job:
                self._jobstore.remove_job(job_id)
        else:
            # replace job, but keep the next run time
            next_run_time = job.next_run_time if job else undefined

            job = self._scheduler.add_job(
                func,
                'interval',
                args=(self._registry,),
                id=job_id,
                name=job_name,
                jitter=jitter,
                minutes=intervals_min[job_id],
                max_instances=1,
                next_run_time=next_run_time,
                misfire_grace_time=None,
                coalesce=True,
                replace_existing=True,
            )
            self._registry.set_job(job)

        self._job_setup_todo.discard(job_id)

    def _on_job_error(self, event: JobExecutionEvent):
        """Announce a failed task on the message stream."""

        job = self._scheduler.get_job(event.job_id)
        if isinstance(event.exception, TaskError):
            reason = str(event.exception)
        else:
            reason = '{}: {}'.format(type(event.exception).__name__, str(event.exception))

        self._emitter.submit_event(
            'task-failed',
            {
                'job_id': event.job_id,
                'job_name': job.name if job else event.job_id,
                'reason': reason,
            },
        )

    def run(self):
        try:
            asyncio.get_event_loop().run_forever()
        except (KeyboardInterrupt, SystemExit):
            pass
