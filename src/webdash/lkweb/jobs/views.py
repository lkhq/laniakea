# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import math

from flask import Blueprint, abort, current_app, render_template

from laniakea.db import (
    Job,
    JobKind,
    JobResult,
    JobStatus,
    SparkWorker,
    SourcePackage,
    ImageBuildRecipe,
    session_scope,
)
from laniakea.utils import get_dir_shorthand_for_uuid

from ..utils import is_uuid, humanized_timediff

jobs = Blueprint('jobs', __name__, url_prefix='/jobs')


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
        jobs_per_page = 50
        jobs_total = (
            session.query(Job).filter(Job.status != JobStatus.DONE).filter(Job.status != JobStatus.TERMINATED).count()
        )
        page_count = math.ceil(jobs_total / jobs_per_page)

        jobs = (
            session.query(Job)
            .filter(Job.status != JobStatus.DONE)
            .filter(Job.status != JobStatus.TERMINATED)
            .order_by(Job.time_created)
            .slice((page - 1) * jobs_per_page, page * jobs_per_page)
            .all()
        )

        return render_template(
            'jobs/queue.html',
            JobStatus=JobStatus,
            humanized_timediff=humanized_timediff,
            session=session,
            title_for_job=title_for_job,
            jobs=jobs,
            jobs_per_page=jobs_per_page,
            jobs_total=jobs_total,
            current_page=page,
            page_count=page_count,
        )


@jobs.route('/workers')
def workers():
    with session_scope() as session:
        workers = session.query(SparkWorker).all()

        return render_template('jobs/workers.html', workers=workers, humanized_timediff=humanized_timediff)


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
        if job.result == JobResult.SUCCESS or job.result == JobResult.FAILURE:
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
            if job.data:
                suite_name = job.data.get('suite')

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
