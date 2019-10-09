#!/usr/bin/env python3
#
# Copyright (C) 2016-2019 Matthias Klumpp <matthias@tenstral.net>
#
# Licensed under the GNU Lesser General Public License Version 3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the license, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
thisfile = __file__
if not os.path.isabs(thisfile):
    thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(thisfile), '..')))

import logging as log
from argparse import ArgumentParser
from laniakea import LkModule
from laniakea.utils import any_arch_matches
from laniakea.db import session_factory, config_get_value, ArchiveSuite, ArchiveRepository, SourcePackage, BinaryPackage, \
    DebcheckIssue, PackageType, Job, JobStatus, JobKind
from sqlalchemy.orm import undefer


def get_newest_sources_index(session, repo, suite):
    '''
    Create an index of the most recent source packages, using
    the source-UUID of source packages.
    '''
    from laniakea.utils import compare_versions

    res_spkgs = {}
    spkgs = session.query(SourcePackage) \
        .options(undefer(SourcePackage.version)) \
        .options(undefer(SourcePackage.architectures)) \
        .filter(SourcePackage.suites.any(ArchiveSuite.id == suite.id)) \
        .filter(SourcePackage.repo_id == repo.id) \
        .order_by(SourcePackage.version.desc()) \
        .all()

    for pkg in spkgs:
        epkg = res_spkgs.get(pkg.uuid)
        if epkg and compare_versions(pkg.version, epkg.version) <= 0:
            # don't override if the existing version is newer
            continue
        res_spkgs[pkg.uuid] = pkg

    return res_spkgs


def binaries_exist_for_package(session, repo, spkg, arch):
    '''
    Get list of binary packages built for the given source package.
    '''

    eq = session.query(BinaryPackage) \
        .filter(BinaryPackage.repo_id == repo.id) \
        .filter(BinaryPackage.source_name == spkg.name) \
        .filter(BinaryPackage.source_version == spkg.version) \
        .filter(BinaryPackage.architecture == arch).exists()
    return session.query(eq).scalar()


def debcheck_has_issues_for_package(session, suite, spkg, arch):
    '''
    Get Debcheck issues related to the given source package.
    '''

    eq = session.query(DebcheckIssue) \
        .filter(DebcheckIssue.package_type == PackageType.SOURCE) \
        .filter(DebcheckIssue.suite_id == suite.id) \
        .filter(DebcheckIssue.package_name == spkg.name) \
        .filter(DebcheckIssue.package_version == spkg.version) \
        .filter(DebcheckIssue.architectures.any(arch.name)).exists()
    return session.query(eq).scalar()


def schedule_build_for_arch(session, repo, spkg, arch, incoming_suite, *, enforce_indep=False, arch_all=None, simulate=False):
    '''
    Schedule a job for the given architecture, if the
    package can be built on it and no prior job was scheduled.
    '''

    # check if this package has binaries installed already, in that case we don't
    # need a rebuild.
    if binaries_exist_for_package(session, repo, spkg, arch):
        return False

    if enforce_indep:
        assert arch_all  # we need to know the entity of arch:all here, not supplying it is a bug
        # we were requested to inforce arch-independent package built on a non-affinity architecture.
        # we have to verify that and check if something hasn't already built arch:all packages in a
        # previous run (or via a package sync) and revise that enforcement hint in such a case.
        if binaries_exist_for_package(session, repo, spkg, arch_all):
            enforce_indep = False

    # we have no binaries, looks like we might need to schedule a build job
    #
    # check if all dependencies are there, if not we might create a job anyway and
    # set it to wait for dependencies to become available
    has_dependency_issues = debcheck_has_issues_for_package(session, incoming_suite, spkg, arch)

    # check if we have already scheduled a job for this in the past and don't create
    # another one in that case
    job = session.query(Job) \
                 .options(undefer(Job.status)) \
                 .options(undefer(Job.result)) \
                 .filter(Job.trigger == spkg.source_uuid) \
                 .filter(Job.version == spkg.version) \
                 .filter(Job.architecture == arch.name) \
                 .order_by(Job.time_created) \
                 .first()
    if job:
        if has_dependency_issues:
            # dependency issues and an already existing job means there is nothing to
            # do for us
            if job.has_result() and job.is_failed() and job.status != JobStatus.DEPWAIT:
                # the job ran, likely failed due to missing dependencies,
                # and was not set back to dependency-wait status, so we'll do that now
                job.status = JobStatus.DEPWAIT
            return False
        elif job.status == JobStatus.DEPWAIT:
            # no dependency issues anymore, but the job is waiting for dependencies?
            # unblock it!
            job.status = JobStatus.WAITING
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

        data = {'suite': incoming_suite.name}
        if enforce_indep:
            data['do_indep'] = True  # enforce arch:all build, no matter what Lighthouse thinks
        job.data = data

        if has_dependency_issues:
            job.status = JobStatus.DEPWAIT
        session.add(job)

    return True


def delete_orphaned_jobs(session, simulate=False):
    '''
    Clean up jobs thet were scheduled for source packages that have meanwhile been removed from
    the archive entirely.
    '''

    pending_jobs = session.query(Job) \
        .filter(Job.module == LkModule.ARIADNE) \
        .filter(Job.status.in_((JobStatus.UNKNOWN, JobStatus.WAITING, JobStatus.DEPWAIT))).all()
    for job in pending_jobs:
        # The job only is an orphan if the source package triggering it
        # does no longer exist with the given version number.
        spkg = session.query(SourcePackage) \
            .filter(SourcePackage.source_uuid == job.trigger) \
            .filter(SourcePackage.version == job.version) \
            .one_or_none()
        if spkg:
            continue

        # we have no source package for this job, so this job is orphaned and can never be processed.
        # This happens if a job is scheduled for a package, and then the package is removed entirely from
        # all archive suites while the job has not finished yet.
        if simulate:
            log.info('Delete orphaned job: {}'.format(str(job.uuid)))
        else:
            log.debug('Deleting orphaned job: {}'.format(str(job.uuid)))
            session.delete(job)


def schedule_builds_for_suite(repo_name, incoming_suite_name, simulate=False, limit_architecture=None, limit_count=0):
    '''
    Schedule builds for packages in a particular suite.
    '''

    session = session_factory()

    # where to build pure arch:all packages?
    arch_indep_affinity = config_get_value(LkModule.ARIADNE, 'indep_arch_affinity')

    repo = session.query(ArchiveRepository) \
        .filter(ArchiveRepository.name == repo_name).one()
    incoming_suite = session.query(ArchiveSuite) \
        .filter(ArchiveSuite.name == incoming_suite_name).one_or_none()
    if not incoming_suite:
        log.error('Incoming suite "{}" was not found in the database.'.format(incoming_suite_name))
        return False

    src_packages = get_newest_sources_index(session, repo, incoming_suite)

    arch_all = None
    for arch in incoming_suite.architectures:
        if arch.name == 'all':
            arch_all = arch
            break
    if not arch_all:
        log.warning('Suite "{}" does not have arch:all in its architecture set, some packages can not be built.'.format(incoming_suite.name))

    if simulate:
        log.info('Simulation, not scheduling any actual builds.')
    if limit_architecture:
        log.info('Only scheduling builds for architecture "{}".'.format(limit_architecture))
    if limit_count > 0:
        log.info('Only scheduling maximally {} builds.'.format(limit_count))

    scheduled_count = 0
    for spkg in src_packages.values():
        # if the package is arch:all only, it needs a dedicated build job
        if len(spkg.architectures) == 1 and spkg.architectures[0] == 'all':
            if not arch_all:
                continue
            if limit_architecture and limit_architecture != 'all':
                continue  # Skip, we are not scheduling builds for arch:all

            # check if we can build the package on the current architecture
            if not any_arch_matches(arch_all.name, spkg.architectures):
                continue

            if schedule_build_for_arch(session, repo, spkg, arch_all, incoming_suite, simulate=simulate):
                scheduled_count += 1

            if limit_count > 0 and scheduled_count >= limit_count:
                break

            continue

        # deal with all other architectures
        build_for_archs = []
        for arch in incoming_suite.architectures:
            # The pseudo-architecture arch:all is treated specially
            if arch.name == 'all':
                continue

            if limit_architecture and limit_architecture != arch.name:
                continue  # Skip, we are not scheduling builds for this architecture

            # check if we can build the package on the current architecture
            if any_arch_matches(arch.name, spkg.architectures):
                build_for_archs.append(arch)

        force_indep = False
        if len(build_for_archs) == 1 and 'all' in spkg.architectures and build_for_archs[0].name != arch_indep_affinity:
            # if we only build for one non-all architecture, and that is not already
            # our arch-indep affinity (in which case the arch:all packages would be built regardless), then we
            # need to add a marker to enforce a built of arch-independent packages on a non-affinity architecture
            # The shedule function will take care to see if binaries for all already exist in that case
            #
            # NOTE: We intentionally ignore the case where a package has an architecture restriction like "all bar baz" where we only
            # can build arch:foo - presumably building this package won't be useful, if we only can use the arch:all parts of a package
            # that's not for us in every other regard.
            force_indep = True

        for arch in build_for_archs:
            if schedule_build_for_arch(session,
                                       repo,
                                       spkg,
                                       arch,
                                       incoming_suite,
                                       enforce_indep=force_indep,
                                       arch_all=arch_all,
                                       simulate=simulate):
                scheduled_count += 1

            if limit_count > 0 and scheduled_count >= limit_count:
                break

        if limit_count > 0 and scheduled_count >= limit_count:
            break

    # cleanup
    delete_orphaned_jobs(session, simulate)

    # write all changes to database
    session.commit()

    log.info('Scheduled {} build jobs.'.format(scheduled_count))

    return True


def schedule_builds(repo_name, simulate=False, limit_architecture=None, limit_count=0):
    '''
    Schedule builds for packages in the incoming suite.
    '''

    session = session_factory()

    # FIXME: We need much better ways to select the right suite to synchronize with
    incoming_suites = session.query(ArchiveSuite) \
        .filter(ArchiveSuite.accept_uploads == True).all()  # noqa: E712

    for incoming_suite in incoming_suites:
        if not schedule_builds_for_suite(repo_name, incoming_suite.name, simulate, limit_architecture, limit_count):
            return False
    return True


def command_run(options):
    ''' Schedule package builds '''

    # FIXME: Don't hardcode the "master" repository here, fully implement
    # the "multiple repositories" feature
    repo_name = 'master'

    suite_name = options.suite
    limit_count = options.limit_count
    if not limit_count:
        limit_count = 0

    ret = False
    if not suite_name:
        ret = schedule_builds(repo_name, options.simulate, options.limit_arch, limit_count)
    else:
        ret = schedule_builds_for_suite(repo_name, suite_name, options.simulate, options.limit_arch, limit_count)
    if not ret:
        sys.exit(3)


def create_parser(formatter_class=None):
    ''' Create Ariadne CLI argument parser '''

    parser = ArgumentParser(description='Schedule package build jobs.')
    subparsers = parser.add_subparsers(dest='sp_name', title='subcommands')

    # generic arguments
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Enable debug messages.')
    parser.add_argument('--version', action='store_true', dest='show_version',
                        help='Display the version of Laniakea itself.')

    sp = subparsers.add_parser('run', help='Trigger package build jobs for the incoming suite or a specific suite.')
    sp.add_argument('suite', type=str, help='The suite to schedule builds for.', nargs='?')
    sp.add_argument('--simulate', action='store_true', dest='simulate',
                    help='Run simulation, don\'t schedule any jobs and instead just display what would be done.')
    sp.add_argument('--limit-count', type=int, dest='limit_count',
                    help='Limit the amount of builds scheduled at a time to a certain number.')
    sp.add_argument('--limit-architecture', type=str, dest='limit_arch',
                    help='Only schedule builds for the selected architecture.')
    sp.set_defaults(func=command_run)

    return parser


def check_print_version(options):
    if options.show_version:
        from laniakea import __version__
        print(__version__)
        sys.exit(0)


def check_verbose(options):
    if options.verbose:
        log.basicConfig(level=log.DEBUG, format="[%(levelname)s] %(message)s")
        from laniakea.logging import set_verbose
        set_verbose(True)


def run(args):
    if len(args) == 0:
        print('Need a subcommand to proceed!')
        sys.exit(1)

    log.basicConfig(level=log.INFO, format="[%(levelname)s] %(message)s")

    parser = create_parser()

    args = parser.parse_args(args)
    check_print_version(args)
    check_verbose(args)
    args.func(args)


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
