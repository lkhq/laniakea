# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
from sqlalchemy.orm import undefer
from laniakea.db import session_scope, Job, JobStatus, JobResult
from .utils import print_note


def job_retry(options):
    job_uuid = options.retry
    if not job_uuid:
        print('No job ID to retry was set!')
        sys.exit(1)

    with session_scope() as session:
        job = session.query(Job) \
                     .options(undefer(Job.status)) \
                     .options(undefer(Job.result)) \
                     .filter(Job.uuid == job_uuid) \
                     .one_or_none()
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


def module_job_init(options):
    ''' Modify Laniakea Jobs '''

    if options.retry:
        job_retry(options)
    else:
        print('No action selected.')
        sys.exit(1)


def add_cli_parser(parser):
    sp = parser.add_parser('job', help='Modify Spark jobs')

    sp.add_argument('--retry', type=str, dest='retry',
                    help='Retry an existing job and set its state back to waiting, so it gets rescheduled.')

    sp.set_defaults(func=module_job_init)
