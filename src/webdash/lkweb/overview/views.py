# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from datetime import datetime

import pytz
import humanize
import sqlalchemy
from flask import Blueprint, render_template
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from laniakea import LocalConfig
from laniakea.db import (
    BinaryPackage,
    ArchiveRepository,
    ArchiveRepoSuiteSettings,
    session_scope,
)

from ..extensions import cache

overview = Blueprint('overview', __name__)
g_jobstore = None  # the jobstore can only be loaded once, so we globally cache it


def get_scheduler_jobstore():
    from laniakea.db import Base, Database

    global g_jobstore
    if g_jobstore is None:
        db = Database()
        g_jobstore = SQLAlchemyJobStore(engine=db.engine, tablename='maintenance_jobs', metadata=Base.metadata)
    return g_jobstore


def humanized_job_timediff(job):
    """
    Get time when the job will run next in a human-readable format
    as a string.
    """
    if not job:
        return 'Never'

    timediff = datetime.now(pytz.utc).replace(microsecond=0) - job.next_run_time.astimezone(pytz.utc)
    return humanize.naturaltime(timediff)


@overview.route('/')
@cache.cached(timeout=10)
def index():
    lconf = LocalConfig()
    with session_scope() as session:
        master_repo_id = (
            session.query(ArchiveRepository.id).filter(ArchiveRepository.name == lconf.master_repo_name).one()[0]
        )
        repo_count = session.query(ArchiveRepository.id).count()
        dev_target_rss = (
            session.query(ArchiveRepoSuiteSettings)
            .filter(
                ArchiveRepoSuiteSettings.repo.has(id=master_repo_id),
                ArchiveRepoSuiteSettings.repo.has(is_debug=False),
                ArchiveRepoSuiteSettings.devel_target == True,  # noqa: E712
            )
            .first()
        )
        dev_target = None
        if dev_target_rss:
            dev_target = dev_target_rss.suite

        package_count = session.query(BinaryPackage.uuid).distinct(BinaryPackage.name).count()

        # fetch info about scheduled maintenance tasks
        jobstore = get_scheduler_jobstore()
        scheduler_configured = True
        rubicon_nextrun_time = 'disabled'
        publish_nextrun_time = 'disabled'
        spears_nextrun_time = 'disabled'
        debcheck_nextrun_time = 'disabled'
        synchrotron_nextrun_time = 'disabled'
        expire_nextrun_time = 'disabled'
        try:
            job = jobstore.lookup_job('rubicon')
        except sqlalchemy.exc.ProgrammingError:
            # the jobs table likely hasn't been created yet, so we will make no further attempts to fetch its data
            scheduler_configured = False
        if scheduler_configured:
            rubicon_nextrun_time = humanized_job_timediff(job)
            job = jobstore.lookup_job('publish-repos')
            publish_nextrun_time = humanized_job_timediff(job)

            job = jobstore.lookup_job('expire-repos')
            expire_nextrun_time = humanized_job_timediff(job)

            job = jobstore.lookup_job('spears-migrate')
            spears_nextrun_time = humanized_job_timediff(job)

            job = jobstore.lookup_job('debcheck')
            debcheck_nextrun_time = humanized_job_timediff(job)

            job = jobstore.lookup_job('synchrotron-autosync')
            synchrotron_nextrun_time = humanized_job_timediff(job)

        return render_template(
            'index.html',
            repo_count=repo_count,
            dev_target=dev_target,
            package_count=package_count,
            rubicon_nextrun_time=rubicon_nextrun_time,
            publish_nextrun_time=publish_nextrun_time,
            expire_nextrun_time=expire_nextrun_time,
            spears_nextrun_time=spears_nextrun_time,
            debcheck_nextrun_time=debcheck_nextrun_time,
            synchrotron_nextrun_time=synchrotron_nextrun_time,
        )
