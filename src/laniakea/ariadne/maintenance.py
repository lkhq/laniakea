# -*- coding: utf-8 -*-
#
# Copyright (C) 2023-2024 Matthias Klumpp <matthias.klumpp@puri.sm>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
from datetime import UTC, datetime, timedelta

from laniakea import LkModule, LocalConfig
from laniakea.db import (
    Job,
    JobKind,
    JobResult,
    JobStatus,
    SourcePackage,
    config_get_value,
)
from laniakea.utils import get_dir_shorthand_for_uuid
from laniakea.logging import log


def remove_superfluous_pending_jobs(session, simulate: bool = False, arch_indep_affinity: str | None = None):
    """Remove pending jobs that are no longer needed.

    Pending jobs may become superfluous because their binaries have shown up by other means (e.g. due to
    a manual upload), or because the source package that triggered them is no longer available.

    :param session: A SQLAlchemy session
    :param simulate: Do not perform any changes, just log what would be done
    :param arch_indep_affinity: The architecture to use for arch-independent packages.
    """

    if not arch_indep_affinity:
        arch_indep_affinity = config_get_value(LkModule.ARIADNE, 'indep_arch_affinity')

    pending_jobs = (
        session.query(Job)
        .filter(Job.module == LkModule.ARIADNE)
        .filter(Job.status.in_((JobStatus.UNKNOWN, JobStatus.WAITING, JobStatus.DEPWAIT)))
        .all()
    )
    for job in pending_jobs:
        # The job only is an orphan if the source package triggering it
        # does no longer exist with the given version number.
        spkg = (
            session.query(SourcePackage)
            .filter(SourcePackage.source_uuid == job.trigger)
            .filter(SourcePackage.version == job.version)
            .one_or_none()
        )
        if spkg:
            # check if we have binaries on the requested architecture,
            # if so, this job is also no longer needed and can be removed.
            binaries_available = False
            for bin in spkg.binaries:
                bin_arch = bin.architecture.name
                if bin_arch == 'all':
                    bin_arch = arch_indep_affinity
                if bin_arch == job.architecture:
                    binaries_available = True
                    break
            if not binaries_available:
                continue

        # we have no source package for this job, so this job is orphaned and can never be processed.
        # This happens if a job is scheduled for a package, and then the package is removed entirely from
        # all archive suites while the job has not finished yet.
        if simulate:
            log.info('Delete orphaned pending job: {}'.format(str(job.uuid)))
        else:
            log.debug('Deleting orphaned pending job: {}'.format(str(job.uuid)))
            session.delete(job)


def delete_orphaned_jobs(
    session,
    simulate: bool = False,
):
    """Expire records of all jobs that no longer have a source package in the archive.

    :param session: A SQLAlchemy session
    :param simulate: Do not perform any changes, just log what would be done
    """

    lconf = LocalConfig()
    # find all jobs where the source package has gone missing
    pkgbuild_jobs = session.query(Job).filter(Job.module == LkModule.ARIADNE, Job.kind == JobKind.PACKAGE_BUILD).all()
    for job in pkgbuild_jobs:
        spkg = (
            session.query(SourcePackage)
            .filter(SourcePackage.source_uuid == job.trigger)
            .filter(SourcePackage.version == job.version)
            .one_or_none()
        )
        if not spkg:
            log.info(f'Deleting old job {job.uuid} (package that triggered it is no longer available)')

            # don't perform any action if we're just simulating
            if simulate:
                continue

            # remove log files from disk, if they exist
            job_id = str(job.uuid)
            log_dir = os.path.join(lconf.logs_metadata_dir, get_dir_shorthand_for_uuid(job_id))
            firehose_dir = os.path.join(log_dir, 'firehose')

            log_fname = os.path.join(log_dir, job_id + '.log')
            if os.path.exists(log_fname):
                log.debug(f"Removing old log file {log_fname}")
                os.remove(log_fname)
            fh_fname = os.path.join(firehose_dir, job_id + '.firehose.xml')
            if os.path.exists(fh_fname):
                log.debug(f"Removing old firehose file {fh_fname}")
                os.remove(fh_fname)

            # drop the job
            session.delete(job)


def retry_stalled_jobs(
    session,
    simulate: bool = False,
):
    """Reschedule all jobs that have been in a running/accepted state for too long.

    :param session: A SQLAlchemy session
    :param simulate: Do not perform any changes, just log what would be done
    """

    # we assume that anything that is stuck in running or scheduled for two weeks is probably stalled for some reason
    fourteen_days_ago = datetime.now(UTC) - timedelta(days=14)
    stalled_jobs = (
        session.query(Job)
        .filter(Job.status.in_((JobStatus.RUNNING, JobStatus.SCHEDULED)))
        .filter(Job.time_assigned <= fourteen_days_ago)
        .all()
    )

    for job in stalled_jobs:
        log.info(f'Rescheduling stalled job: {job.uuid}')

        # don't perform any action if we're just simulating
        if simulate:
            continue

        # if we are here, it should be safe to reschedule the job
        job.status = JobStatus.WAITING
        job.result = JobResult.UNKNOWN
        job.time_assigned = None
        job.time_finished = None
        job.latest_log_excerpt = 'Job has been rescheduled due to inactivity'
