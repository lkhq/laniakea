# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import json
import math
from enum import Enum, auto
from datetime import datetime, timedelta

from flask import Blueprint, abort, request, current_app, render_template

import laniakea.typing as T
from laniakea.db import (
    Job,
    JobKind,
    JobResult,
    JobStatus,
    PackageType,
    SparkWorker,
    DebcheckIssue,
    SourcePackage,
    StatsEventKind,
    ImageBuildRecipe,
    ArchiveArchitecture,
    session_scope,
    make_stats_key_jobqueue,
)
from laniakea.utils import get_dir_shorthand_for_uuid

from ..utils import is_uuid, humanized_timediff, fetch_statistics_for
from ..extensions import cache

jobs = Blueprint('jobs', __name__, url_prefix='/jobs')


class JobQueueState(Enum):
    PENDING = auto()
    PENDING_BLOCKED = auto()
    COMPLETED = auto()


def fetch_queue_statistics_for(
    session, kind: StatsEventKind, arch_name: str, start_at: datetime
) -> list[dict[str, T.Any]] | None:
    stat_key = make_stats_key_jobqueue(kind, arch_name)
    return fetch_statistics_for(session, stat_key, start_at)


@cache.cached(timeout=30 * 60, key_prefix='full_job_queue_statistics')
def get_full_queue_statistics(session) -> tuple[str, str]:
    pending_stats = {}
    depwait_stats = {}
    earliest_time = datetime.utcnow() - timedelta(days=365)
    for arch in session.query(ArchiveArchitecture).filter(ArchiveArchitecture.name != 'all').all():
        pending_stats[arch.name] = fetch_queue_statistics_for(
            session, StatsEventKind.JOB_QUEUE_PENDING, arch.name, earliest_time
        )
        depwait_stats[arch.name] = fetch_queue_statistics_for(
            session, StatsEventKind.JOB_QUEUE_DEPWAIT, arch.name, earliest_time
        )
    return json.dumps(pending_stats), json.dumps(depwait_stats)


def title_for_job(session, job):
    '''
    Get a human readble title for the given job.
    '''

    title = 'Job for {}'.format(job.module)
    if job.kind == JobKind.PACKAGE_BUILD:
        spkg = (
            session.query(SourcePackage)
            .filter(SourcePackage.source_uuid == job.trigger)
            .filter(SourcePackage.version == job.version)
            .one_or_none()
        )
        if not spkg:
            return title
        return 'Build {} {} on {}'.format(spkg.name, job.version, job.architecture)
    elif job.kind == JobKind.OS_IMAGE_BUILD:
        recipe = session.query(ImageBuildRecipe).filter(ImageBuildRecipe.uuid == job.trigger).one_or_none()
        if not recipe:
            return title
        return 'OS Image {}'.format(recipe.name)

    return title


@jobs.route('/queue/<int:page>')
def queue(page):
    with session_scope() as session:
        queue_state = JobQueueState.PENDING_BLOCKED if request.args.get('blocked') == 'true' else JobQueueState.PENDING
        jobs_per_page = 50
        jobs_base_q = session.query(Job).filter(Job.status != JobStatus.DONE, Job.status != JobStatus.TERMINATED)
        if queue_state == JobQueueState.PENDING:
            jobs_base_q = jobs_base_q.filter(Job.status != JobStatus.DEPWAIT)

        jobs_total = jobs_base_q.count()
        page_count = math.ceil(jobs_total / jobs_per_page)

        jobs = jobs_base_q.order_by(Job.time_created).slice((page - 1) * jobs_per_page, page * jobs_per_page).all()

        return render_template(
            'jobs/queue.html',
            JobStatus=JobStatus,
            JobResult=JobResult,
            JobQueueState=JobQueueState,
            humanized_timediff=humanized_timediff,
            session=session,
            queue_state=queue_state,
            title_for_job=title_for_job,
            jobs=jobs,
            jobs_per_page=jobs_per_page,
            jobs_total=jobs_total,
            current_page=page,
            page_count=page_count,
        )


@jobs.route('/queue/completed/<int:page>')
def list_completed(page):
    with session_scope() as session:
        jobs_per_page = 50
        max_pages_count = 3
        jobs_base_q = (
            session.query(Job)
            .filter(Job.status.in_((JobStatus.DONE, JobStatus.TERMINATED)), ~Job.time_finished.is_(None))
            .order_by(Job.time_finished.desc())
            .limit(jobs_per_page * max_pages_count)
        )
        jobs_total = jobs_base_q.count()
        page_count = math.ceil(jobs_total / jobs_per_page)

        jobs = jobs_base_q.slice((page - 1) * jobs_per_page, page * jobs_per_page).all()

        return render_template(
            'jobs/queue.html',
            JobStatus=JobStatus,
            JobResult=JobResult,
            JobQueueState=JobQueueState,
            humanized_timediff=humanized_timediff,
            session=session,
            queue_state=JobQueueState.COMPLETED,
            title_for_job=title_for_job,
            jobs=jobs,
            jobs_per_page=jobs_per_page,
            jobs_total=jobs_total,
            current_page=page,
            page_count=page_count,
        )


@jobs.route('/queue/stats')
@cache.cached(timeout=10 * 60)
def queue_stats():
    with session_scope() as session:
        pending_stats, depwait_stats = get_full_queue_statistics(session)

        return render_template(
            'jobs/queue_stats.html',
            pending_stats=pending_stats,
            depwait_stats=depwait_stats,
        )


def prefix_list_entries(lst, prefix: str) -> list[str]:
    return [prefix + e for e in lst]


@jobs.route('/workers')
def workers():
    with session_scope() as session:
        workers = session.query(SparkWorker).all()

        return render_template(
            'jobs/workers.html',
            workers=workers,
            humanized_timediff=humanized_timediff,
            prefix_list_entries=prefix_list_entries,
        )


@jobs.route('/job/<uuid>')
def job(uuid):
    if not is_uuid(uuid):
        abort(404)

    with session_scope() as session:
        job = session.query(Job).filter(Job.uuid == uuid).one_or_none()
        if not job:
            abort(404)

        worker = session.query(SparkWorker).filter(SparkWorker.uuid == job.worker).one_or_none()

        log_url = None
        firehose_url = None
        if job.result in (JobResult.SUCCESS, JobResult.FAILURE, JobResult.FAILURE_DEPENDENCY):
            log_root = current_app.config['LOG_STORAGE_URL'] + '/' + get_dir_shorthand_for_uuid(job.uuid) + '/'
            log_url = log_root + str(job.uuid) + '.log'
            firehose_url = log_root + 'firehose/' + str(job.uuid) + '.firehose.xml'

        job_title = 'Job for {}'.format(job.module)
        if job.kind == JobKind.PACKAGE_BUILD:
            spkg = (
                session.query(SourcePackage)
                .filter(SourcePackage.source_uuid == job.trigger)
                .filter(SourcePackage.version == job.version)
                .one_or_none()
            )
            if spkg:
                job_title = 'Build {} {} on {}'.format(spkg.name, job.version, job.architecture)

            suite_name = 'unknown'
            if job.suite:
                suite_name = job.suite.name

            dep_issues = []
            if spkg and job.suite:
                suite_name = job.suite.name
                dep_issues = (
                    session.query(DebcheckIssue)
                    .filter(DebcheckIssue.package_type == PackageType.SOURCE)
                    .filter(DebcheckIssue.suite_id == job.suite.id)
                    .filter(DebcheckIssue.package_name == spkg.name)
                    .filter(DebcheckIssue.package_version == spkg.version)
                    .filter(DebcheckIssue.architectures.overlap([job.architecture, 'any']))
                    .all()
                )

            return render_template(
                'jobs/job_pkgbuild.html',
                PackageType=PackageType,
                humanized_timediff=humanized_timediff,
                JobStatus=JobStatus,
                JobResult=JobResult,
                job=job,
                job_title=job_title,
                worker=worker,
                spkg=spkg,
                suite_name=suite_name,
                dep_issues=dep_issues,
                log_url=log_url,
                firehose_url=firehose_url,
            )
        elif job.kind == JobKind.OS_IMAGE_BUILD:
            recipe = session.query(ImageBuildRecipe).filter(ImageBuildRecipe.uuid == job.trigger).one_or_none()
            if recipe:
                job_title = 'OS Image {}'.format(recipe.name)

            return render_template(
                'jobs/job_osimage.html',
                humanized_timediff=humanized_timediff,
                JobStatus=JobStatus,
                JobResult=JobResult,
                job=job,
                job_title=job_title,
                worker=worker,
                recipe=recipe,
                log_url=log_url,
            )
        else:
            return render_template(
                'jobs/job_generic.html',
                humanized_timediff=humanized_timediff,
                JobStatus=JobStatus,
                JobResult=JobResult,
                job=job,
                job_title=job_title,
                worker=worker,
                log_url=log_url,
            )


@jobs.route('/job/log/<uuid>')
def view_log(uuid):
    if not is_uuid(uuid):
        abort(404)

    with session_scope() as session:
        job = session.query(Job).filter(Job.uuid == uuid).one_or_none()
        if not job:
            abort(404)

        log_url = None
        if job.result in (JobResult.SUCCESS, JobResult.FAILURE, JobResult.FAILURE_DEPENDENCY):
            log_root = current_app.config['LOG_STORAGE_URL'] + '/' + get_dir_shorthand_for_uuid(job.uuid) + '/'
            log_url = log_root + str(job.uuid) + '.log'
            firehose_url = log_root + 'firehose/' + str(job.uuid) + '.firehose.xml'

        log_title = str(uuid)[:11]
        return render_template(
            'jobs/logviewer.html',
            humanized_timediff=humanized_timediff,
            job=job,
            log_title=log_title,
            log_url=log_url,
            firehose_url=firehose_url,
        )
