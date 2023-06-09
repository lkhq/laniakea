# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import json
import math
from datetime import datetime, timedelta

from flask import Blueprint, abort, request, current_app, render_template
from sqlalchemy import func

import laniakea.typing as T
from laniakea.db import (
    Job,
    JobKind,
    JobResult,
    JobStatus,
    StatsEntry,
    SparkWorker,
    SourcePackage,
    StatsEventKind,
    ImageBuildRecipe,
    ArchiveArchitecture,
    session_scope,
    make_stats_key_jobqueue,
)
from laniakea.utils import get_dir_shorthand_for_uuid

from ..utils import is_uuid, humanized_timediff
from ..extensions import cache

jobs = Blueprint('jobs', __name__, url_prefix='/jobs')


def fetch_queue_statistics_for(
    session, kind: StatsEventKind, arch_name: str, start_at: datetime
) -> list[dict[str, T.Any]] | None:
    stat_key = make_stats_key_jobqueue(kind, arch_name)
    values = (
        session.query(func.extract('epoch', StatsEntry.time), StatsEntry.value)
        .filter(StatsEntry.key == stat_key, StatsEntry.time > start_at)
        .all()
    )
    if not values:
        return None
    return [{'x': int(v[0]), 'y': v[1]} for v in values]


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
        show_depwait = request.args.get('blocked') == 'true'
        jobs_per_page = 50
        jobs_base_q = session.query(Job).filter(Job.status != JobStatus.DONE, Job.status != JobStatus.TERMINATED)
        if not show_depwait:
            jobs_base_q = jobs_base_q.filter(Job.status != JobStatus.DEPWAIT)

        jobs_total = jobs_base_q.count()
        page_count = math.ceil(jobs_total / jobs_per_page)

        jobs = jobs_base_q.order_by(Job.time_created).slice((page - 1) * jobs_per_page, page * jobs_per_page).all()

        return render_template(
            'jobs/queue.html',
            JobStatus=JobStatus,
            humanized_timediff=humanized_timediff,
            session=session,
            show_blocked=show_depwait,
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
        if job.result in (JobResult.SUCCESS, JobResult.FAILURE, JobResult.FAILURE_DEPENDENCY):
            log_url = (
                current_app.config['LOG_STORAGE_URL']
                + '/'
                + get_dir_shorthand_for_uuid(job.uuid)
                + '/'
                + str(job.uuid)
                + '.log'
            )

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

            return render_template(
                'jobs/job_pkgbuild.html',
                humanized_timediff=humanized_timediff,
                JobStatus=JobStatus,
                JobResult=JobResult,
                job=job,
                job_title=job_title,
                worker=worker,
                spkg=spkg,
                suite_name=suite_name,
                log_url=log_url,
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
