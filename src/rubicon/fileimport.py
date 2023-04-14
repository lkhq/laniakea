# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import sys
import logging as log
from glob import glob

import laniakea.typing as T
from laniakea import LkModule
from laniakea.db import (
    Job,
    JobKind,
    JobResult,
    SourcePackage,
    ArchiveRepository,
    session_scope,
)
from laniakea.dud import Dud
from laniakea.utils import safe_rename, random_string, get_dir_shorthand_for_uuid
from laniakea.msgstream import EventEmitter

from .rubiconfig import RubiConfig
from .import_package import handle_package_uploads


def accept_dud_upload(conf: RubiConfig, repo: ArchiveRepository, dud: Dud, event_emitter: EventEmitter):
    """
    Accept the DUD upload and move its data to the right places.
    """

    job_result_str = dud.get('X-Spark-Result')
    job_id = dud.get('X-Spark-Job')
    if not job_result_str:
        job_result_str = 'success' if dud.get('X-Spark-Success') == 'Yes' else 'failure'

    job_result = JobResult.FAILURE
    if job_result_str == 'success':
        job_result = JobResult.SUCCESS
    elif job_result_str == 'depwait':
        job_result = JobResult.FAILURE_DEPENDENCY

    # mark job as accepted and done
    with session_scope() as session:
        job = session.query(Job).filter(Job.uuid == job_id).one_or_none()
        if not job:
            log.error('Unable to mark job \'{}\' as done: The Job was not found.'.format(job_id))

            # this is a weird situation, there is no proper way to handle it as this indicates a bug
            # in the Laniakea setup or some other oddity.
            # The least harmful thing to do is to just leave the upload alone and try again later.
            return

        job.result = job_result
        job.latest_log_excerpt = None

        # move the log file and Firehose reports to the log storage
        log_target_dir = os.path.join(conf.log_storage_dir, get_dir_shorthand_for_uuid(job_id))
        firehose_target_dir = os.path.join(log_target_dir, 'firehose')
        for fname in dud.get_files():
            if fname.endswith('.log'):
                os.makedirs(log_target_dir, exist_ok=True)

                # move the logfile to its destination and ensure it is named correctly
                target_fname = os.path.join(log_target_dir, job_id + '.log')
                safe_rename(fname, target_fname, override=True)
            elif fname.endswith('.firehose.xml'):
                os.makedirs(firehose_target_dir, exist_ok=True)

                # move the firehose report to its own directory and rename it
                fh_target_fname = os.path.join(firehose_target_dir, job_id + '.firehose.xml')
                safe_rename(fname, fh_target_fname, override=True)

        # handle different job data
        if job.module == LkModule.ISOTOPE:
            from .import_isotope import handle_isotope_upload

            handle_isotope_upload(
                session,
                success=job_result == JobResult.SUCCESS,
                conf=conf,
                dud=dud,
                job=job,
                event_emitter=event_emitter,
            )

        elif job.kind == JobKind.PACKAGE_BUILD:
            # the package has been imported by Dak, so we just announce this
            # event to the world
            spkg = (
                session.query(SourcePackage)
                .filter(SourcePackage.source_uuid == job.trigger)
                .filter(SourcePackage.version == job.version)
                .one_or_none()
            )
            if spkg:
                suite_target_name = '?'
                if job.data:
                    suite_target_name = job.data.get('suite', '?')

                event_data = {
                    'pkgname': spkg.name,
                    'version': job.version,
                    'architecture': job.architecture,
                    'suite': suite_target_name,
                    'job_id': job_id,
                }
                if job_result == JobResult.SUCCESS:
                    event_emitter.submit_event_for_mod(LkModule.ARCHIVE, 'package-build-success', event_data)
                elif job_result == JobResult.FAILURE:
                    event_emitter.submit_event_for_mod(LkModule.ARCHIVE, 'package-build-failed', event_data)
                elif job_result == JobResult.FAILURE_DEPENDENCY:
                    event_emitter.submit_event_for_mod(LkModule.ARCHIVE, 'package-build-depwait', event_data)
        else:
            event_emitter.submit_event(
                'job-upload-accepted', {'job_id': job_id, 'job_failed': job_result != JobResult.SUCCESS}
            )

    # remove the upload description file from incoming
    os.remove(dud.get_dud_file())

    log.info('%s: Upload `%s` accepted.', repo.name, dud.get_filename())


def reject_dud_upload(
    conf: RubiConfig,
    repo: ArchiveRepository,
    dud: Dud,
    reason: str = 'Unknown',
    event_emitter: T.Optional[EventEmitter] = None,
):
    '''
    If a file has issues, we reject it and put it into the rejected queue.
    '''

    os.makedirs(conf.rejected_dir, exist_ok=True)

    # move the files referenced by the .dud file
    random_suffix = random_string(4)
    for fname in dud.get_files():
        target_fname = os.path.join(conf.rejected_dir, os.path.basename(fname))
        if os.path.isfile(target_fname):
            target_fname = target_fname + '+' + random_suffix

        # move the file to the rejected dir
        safe_rename(fname, target_fname)

    # move the .dud file itself
    target_fname = os.path.join(conf.rejected_dir, dud.get_filename())
    if os.path.isfile(target_fname):
        target_fname = target_fname + '+' + random_suffix
    safe_rename(dud.get_dud_file(), target_fname)

    # also store the reject reason for future reference
    with open(target_fname + '.reason', 'w') as f:
        f.write(reason + '\n')

    log.info('%s: Dud upload `%s` rejected.', repo.name, dud.get_filename())
    if event_emitter:
        event_emitter.submit_event(
            'job-upload-rejected', {'dud_filename': dud.get_filename(), 'reason': reason, 'repo': repo.name}
        )


def import_files_for(
    session, conf: RubiConfig, repo: ArchiveRepository, incoming_dir: T.PathUnion, emitter: EventEmitter
):
    """
    Import files from an untrusted incoming source.

    IMPORTANT: We assume that the uploader can not edit their files post-upload.
    If they could, we would be vulnerable to timing attacks here.
    """

    for dud_file in glob(os.path.join(incoming_dir, '*.dud')):
        dud = Dud(dud_file)

        try:
            dud.validate(keyrings=conf.trusted_gpg_keyrings)
        except Exception as e:
            reason = 'Signature validation failed: {}'.format(str(e))
            reject_dud_upload(conf, repo, dud, reason, emitter)
            continue

        # if we are here, the file is good to go
        accept_dud_upload(conf, repo, dud, emitter)

    changes_fnames = glob(os.path.join(incoming_dir, '*.changes'))
    if changes_fnames:
        handle_package_uploads(session, conf, repo, changes_fnames, event_emitter=emitter)


def import_files(options):
    conf = RubiConfig()

    incoming_dir = options.incoming_dir
    repo_name = options.repo_name
    if not incoming_dir:
        incoming_dir = conf.incoming_dir

    # try to create incoming root directory if it does not exist yet
    if not os.path.isdir(incoming_dir):
        os.makedirs(incoming_dir, exist_ok=True)

    master_repo_name = conf.common_config.master_repo_name
    emitter = EventEmitter(LkModule.RUBICON)
    with session_scope() as session:
        if repo_name:
            repos = session.query(ArchiveRepository).filter(ArchiveRepository.name == repo_name).all()
            if not repos:
                print('Unable to find repository {}!'.format(repo_name), file=sys.stderr)
                sys.exit(1)
        else:
            # we process NEW in all repositories if no filter was set
            repos = session.query(ArchiveRepository).all()

        for repo in repos:
            if repo.name == master_repo_name:
                # for the master repository we process the root directory as well for
                # backwards compatibility
                import_files_for(session, conf, repo, incoming_dir, emitter=emitter)
            repo_incoming_dir = os.path.join(incoming_dir, repo.name)
            if not os.path.isdir(repo_incoming_dir):
                os.makedirs(repo_incoming_dir, exist_ok=True)
            import_files_for(session, conf, repo, repo_incoming_dir, emitter=emitter)
