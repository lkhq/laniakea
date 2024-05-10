# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import sys
import logging as log

import click
from sqlalchemy import and_, func
from sqlalchemy.orm import undefer

from laniakea import LkModule
from laniakea.db import (
    Job,
    JobStatus,
    SourcePackage,
    ArchiveRepoSuiteSettings,
    session_scope,
    config_get_value,
)
from laniakea.utils import process_file_lock
from laniakea.ariadne import schedule_package_builds_for_source


def get_newest_sources_index(session, rss: ArchiveRepoSuiteSettings):
    """
    Create an index of the most recent source packages.
    """

    spkg_filters = [
        SourcePackage.repo_id == rss.repo_id,
        SourcePackage.suites.any(id=rss.suite_id),
        SourcePackage.time_deleted.is_(None),
    ]

    spkg_filter_sq = session.query(SourcePackage).filter(*spkg_filters).subquery()
    smv_sq = (
        session.query(spkg_filter_sq.c.name, func.max(spkg_filter_sq.c.version).label('max_version'))
        .group_by(spkg_filter_sq.c.name)
        .subquery('smv_sq')
    )

    # get the latest source packages for this configuration
    latest_spkg = (
        session.query(SourcePackage)
        .options(undefer(SourcePackage.version))
        .options(undefer(SourcePackage.architectures))
        .filter(*spkg_filters)
        .join(
            smv_sq,
            and_(
                SourcePackage.name == smv_sq.c.name,
                SourcePackage.version == smv_sq.c.max_version,
            ),
        )
        .all()
    )

    return latest_spkg


def delete_orphaned_jobs(session, simulate: bool = False, arch_indep_affinity: str | None = None):
    '''
    Clean up jobs that were scheduled for source packages that have meanwhile been removed from
    the archive entirely.
    '''

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
            log.info('Delete orphaned job: {}'.format(str(job.uuid)))
        else:
            log.debug('Deleting orphaned job: {}'.format(str(job.uuid)))
            session.delete(job)


def update_package_build_schedule(
    session, rss: ArchiveRepoSuiteSettings, simulate=False, limit_architecture=None, limit_count=0
) -> int:
    '''
    Schedule builds for packages in a particular suite.
    '''

    # where to build pure arch:all packages?
    arch_indep_affinity = config_get_value(LkModule.ARIADNE, 'indep_arch_affinity')
    src_packages = get_newest_sources_index(session, rss)

    arch_all = None
    for arch in rss.suite.architectures:
        if arch.name == 'all':
            arch_all = arch
            break
    if not arch_all:
        log.warning(
            'Suite "{}" does not have arch:all in its architecture set, some packages can not be built.'.format(
                rss.suite.name
            )
        )

    if simulate:
        log.info('Simulation, not scheduling any actual builds.')
    if limit_architecture:
        log.info('Only scheduling builds for architecture "{}".'.format(limit_architecture))
    if limit_count > 0:
        log.info('Only scheduling maximally {} builds.'.format(limit_count))

    scheduled_count = 0
    for spkg in src_packages:
        scheduled_count += schedule_package_builds_for_source(
            session,
            rss,
            spkg,
            limit_arch_name=limit_architecture,
            arch_all=arch_all,
            simulate=simulate,
            arch_indep_affinity=arch_indep_affinity,
        )
        if limit_count != 0 and scheduled_count >= limit_count:
            break

    # cleanup
    delete_orphaned_jobs(session, simulate, arch_indep_affinity=arch_indep_affinity)

    # write all changes to database
    session.commit()

    if simulate:
        log.info('Would have scheduled {} build jobs.'.format(scheduled_count))
    else:
        log.info('Scheduled {} build jobs.'.format(scheduled_count))

    return scheduled_count


@click.command('update-jobs')
@click.option(
    '--repo',
    'repo_name',
    default=None,
    help='Name of the repository to act on, if not set all repositories will be checked',
)
@click.option(
    '--suite',
    'suite_name',
    default=None,
    help='The suite to schedule builds for, if not set all repositories will be checked',
)
@click.option(
    '--simulate',
    'simulate',
    is_flag=True,
    default=False,
    help='Run simulation, don\'t schedule any jobs and instead just display what would be done.',
)
@click.option(
    '--limit-count',
    'limit_count',
    type=int,
    default=0,
    help='Limit the amount of builds scheduled at a time to a certain number.',
)
@click.option(
    '--limit-architecture',
    'limit_arch',
    default=None,
    help='Only schedule builds for the selected architecture.',
)
def update_jobs(
    repo_name: str | None,
    suite_name: str | None,
    limit_count: int = 0,
    limit_arch: str | None = None,
    simulate: bool = False,
):
    """Schedule & update package build jobs."""

    if not limit_count:
        limit_count = 0

    with session_scope() as session:
        all_rss = session.query(ArchiveRepoSuiteSettings).all()

        processed = False
        scheduled_count = 0
        for rss in all_rss:
            if repo_name:
                if rss.repo.name != repo_name:
                    continue
            if suite_name:
                if rss.suite.name != suite_name:
                    continue
            elif not rss.accept_uploads or rss.frozen:
                # we don't process information for frozen suites or suites that don't accept uploads
                continue
            processed = True

            # during long sync operation, we might have a lot of source packages in the archive before
            # the binaries are synced, so to avoid scheduling unnecessary builds we need to wait for any
            # pending sync operation to complete first
            with process_file_lock('sync_{}'.format(rss.repo.name)):
                log.info('Processing {}:{}'.format(rss.repo.name, rss.suite.name))
                scheduled_count += update_package_build_schedule(session, rss, simulate, limit_arch, limit_count)
                if limit_count > 0 and scheduled_count >= limit_count:
                    break

    if not processed:
        if suite_name and repo_name:
            print('Unable to find {}:{} to process build jobs for.'.format(suite_name, repo_name), file=sys.stderr)
        elif repo_name:
            print(
                'Unable to find suites in repository {} to process build jobs for.'.format(repo_name), file=sys.stderr
            )
        elif suite_name:
            print(
                'Unable to find suite {} in any repository to process build jobs for.'.format(suite_name),
                file=sys.stderr,
            )
        sys.exit(3)
