# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
import uuid

import click
from sqlalchemy.orm import undefer

from laniakea.db import Job, JobResult, JobStatus, session_scope

from .utils import print_note


@click.group()
def job():
    '''Manage the Spark job queue.'''


@job.command()
@click.option('--id', '-j', help='The UUID of the job to retry.')
def retry(id):
    '''Retry an existing job.
    Set the job's state back to waiting, so it gets rescheduled.'''
    job_uuid = str(uuid.UUID(id))
    if not job_uuid:
        print('No job ID to retry was set!')
        sys.exit(1)

    with session_scope() as session:
        job = (
            session.query(Job)
            .options(undefer(Job.status))
            .options(undefer(Job.result))
            .filter(Job.uuid == job_uuid)
            .one_or_none()
        )
        if not job:
            print('Did not find job with ID "{}"'.format(job_uuid))
            sys.exit(1)

        if job.status == JobStatus.WAITING:
            print_note('Job is already waiting to be scheduled. Doing nothing.')
            sys.exit(2)
        if job.status == JobStatus.SCHEDULED:
            print_note('Job is already scheduled. Doing nothing.')
            sys.exit(2)
        if job.status == JobStatus.RUNNING:
            print_note('Job is currently running. Doing nothing.')
            sys.exit(2)

        # if we are here, it should be safe to reschedule the job
        job.status = JobStatus.WAITING
        job.result = JobResult.UNKNOWN
        job.time_assigned = None
        job.time_finished = None
        job.latest_log_excerpt = None

        print_note('Job {}/{}::{} was rescheduled.'.format(str(job.module), str(job.kind), str(job.uuid)))
