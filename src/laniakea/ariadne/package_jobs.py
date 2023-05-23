# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

from sqlalchemy.orm import undefer

from laniakea import LkModule
from laniakea.db import (
    Job,
    JobKind,
    JobResult,
    JobStatus,
    PackageType,
    DebcheckIssue,
    SourcePackage,
    ArchiveArchitecture,
    ArchiveRepoSuiteSettings,
    config_get_value,
)
from laniakea.utils import any_arch_matches
from laniakea.archive import binaries_exist_for_package
from laniakea.logging import log


def debcheck_has_issues_for_package(
    session, rss: ArchiveRepoSuiteSettings, spkg: SourcePackage, arch: ArchiveArchitecture
):
    """
    Get Debcheck issues related to the given source package.
    """

    eq = (
        session.query(DebcheckIssue)
        .filter(DebcheckIssue.package_type == PackageType.SOURCE)
        .filter(DebcheckIssue.repo_id == rss.repo.id)
        .filter(DebcheckIssue.suite_id == rss.suite.id)
        .filter(DebcheckIssue.package_name == spkg.name)
        .filter(DebcheckIssue.package_version == spkg.version)
        .filter(DebcheckIssue.architectures.any(arch.name))
        .exists()
    )
    return session.query(eq).scalar()


def schedule_build_for_arch(
    session,
    rss: ArchiveRepoSuiteSettings,
    spkg: SourcePackage,
    arch: ArchiveArchitecture,
    *,
    enforce_indep=False,
    arch_all=None,
    simulate=False,
):
    """
    Schedule a job for the given architecture, if the
    package can be built on it and no prior job was scheduled.
    """

    # check if this package has binaries installed already, in that case we don't
    # need a rebuild.
    if binaries_exist_for_package(session, rss, spkg, arch):
        return False

    if enforce_indep:
        assert arch_all  # we need to know the entity of arch:all here, not supplying it is a bug
        # we were requested to inforce arch-independent package built on a non-affinity architecture.
        # we have to verify that and check if something hasn't already built arch:all packages in a
        # previous run (or via a package sync) and revise that enforcement hint in such a case.
        if binaries_exist_for_package(session, rss, spkg, arch_all):
            enforce_indep = False

    # we have no binaries, looks like we might need to schedule a build job
    #
    # check if all dependencies are there, if not we might create a job anyway and
    # set it to wait for dependencies to become available
    has_dependency_issues = debcheck_has_issues_for_package(session, rss, spkg, arch)

    # check if we have already scheduled a job for this in the past and don't create
    # another one in that case
    job = (
        session.query(Job)
        .options(undefer(Job.status))
        .options(undefer(Job.result))
        .filter(Job.trigger == spkg.source_uuid)
        .filter(Job.version == spkg.version)
        .filter(Job.architecture == arch.name)
        .order_by(Job.time_created)
        .first()
    )
    if job:
        if has_dependency_issues:
            # dependency issues and an already existing job means there is nothing to
            # do for us
            if job.is_failed() and job.status != JobStatus.DEPWAIT:
                # the job ran, likely failed due to missing dependencies,
                # and was not set back to dependency-wait status, so we'll do that now
                job.status = JobStatus.DEPWAIT
            return False
        elif job.status == JobStatus.DEPWAIT:
            # no dependency issues anymore, but the job is waiting for dependencies?
            # unblock it!
            job.status = JobStatus.WAITING
            job.result = JobResult.UNKNOWN
            return True

        # we already have a job, we don't need to create another one
        return False

    # no issues found and a build seems required.
    # let's go!
    if simulate:
        if has_dependency_issues:
            log.info('New dependency-wait job for {} on {}'.format(str(spkg), arch.name))
        else:
            log.info('New actionable job for {} on {}'.format(str(spkg), arch.name))
    else:
        log.debug('Creating new job for {} on {}'.format(str(spkg), arch.name))
        job = Job()
        job.module = LkModule.ARIADNE
        job.kind = JobKind.PACKAGE_BUILD
        job.version = spkg.version
        job.architecture = arch.name
        job.trigger = spkg.source_uuid
        job.suite = rss.suite

        data = {}
        if enforce_indep:
            data['do_indep'] = True  # enforce arch:all build, no matter what Lighthouse thinks
        job.data = data

        if has_dependency_issues:
            job.status = JobStatus.DEPWAIT
        session.add(job)

    return True


def schedule_package_builds_for_source(
    session,
    rss: ArchiveRepoSuiteSettings,
    spkg: SourcePackage,
    *,
    limit_arch_name: str | None = None,
    arch_all: ArchiveArchitecture | None = None,
    simulate: bool = False,
    arch_indep_affinity: str | None = None,
) -> int:
    """
    Schedule a build job for the given source package on the given repo/suite if required.

    :param session: A SQLAlchemy session
    :param rss: The repo/suite to build this package on
    :param spkg: The source package to schedule builds for
    :param limit_arch_name: Limit builds to only the selected architecture
    :param arch_all: Entity of the arch:all architecture
    :param simulate: Whether to only simulate instead of actually scheduling anything.
    :param arch_indep_affinity: Architecture affinity for arch:all-only packages
    :return: The number of scheduled jobs
    """

    if not arch_all:
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

    # if the package is arch:all only, it needs a dedicated build job
    if len(spkg.architectures) == 1 and spkg.architectures[0] == 'all':
        if not arch_all:
            return 0
        if limit_arch_name and limit_arch_name != 'all':
            return 0  # Skip, we are not scheduling builds for arch:all

        # check if we can build the package on the current architecture
        if not any_arch_matches(arch_all.name, spkg.architectures):
            return 0

        return 1 if schedule_build_for_arch(session, rss, spkg, arch_all, simulate=simulate) else 0

    if not arch_indep_affinity:
        arch_indep_affinity = config_get_value(LkModule.ARIADNE, 'indep_arch_affinity')

    # deal with all other architectures
    build_for_archs = []
    scheduled_count = 0
    for arch in rss.suite.architectures:
        # The pseudo-architecture arch:all is treated specially
        if arch.name == 'all':
            continue

        if limit_arch_name and limit_arch_name != arch.name:
            continue  # Skip, we are not scheduling builds for this architecture

        # check if we can build the package on the current architecture
        if any_arch_matches(arch.name, spkg.architectures):
            build_for_archs.append(arch)

    force_indep = False
    if len(build_for_archs) == 1 and 'all' in spkg.architectures and build_for_archs[0].name != arch_indep_affinity:
        # if we only build for one non-all architecture, and that is not already
        # our arch-indep affinity (in which case the arch:all packages would be built regardless), then we
        # need to add a marker to enforce a built of arch-independent packages on a non-affinity architecture
        # The schedule function will take care to see if binaries for all already exist in that case
        #
        # NOTE: We intentionally ignore the case where a package has an architecture restriction like "all bar baz" where we only
        # can build arch:foo - presumably building this package won't be useful, if we only can use the arch:all parts of a package
        # that's not for us in every other regard.
        force_indep = True

    for arch in build_for_archs:
        if schedule_build_for_arch(
            session,
            rss,
            spkg,
            arch,
            enforce_indep=force_indep,
            arch_all=arch_all,
            simulate=simulate,
        ):
            scheduled_count += 1

    return scheduled_count
