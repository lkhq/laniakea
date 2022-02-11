# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import sys
import logging as log
from glob import glob

from laniakea import LkModule
from laniakea.db import Job, JobKind, JobResult, SourcePackage, session_scope
from laniakea.dud import Dud
from laniakea.utils import random_string, get_dir_shorthand_for_uuid
from laniakea.msgstream import EventEmitter

from .utils import safe_rename
from .rubiconfig import RubiConfig


def accept_upload(conf, dud, event_emitter):
    '''
    Accept the upload and move its data to the right places.
    '''

    job_success = dud.get('X-Spark-Success') == 'Yes'
    job_id = dud.get('X-Spark-Job')

    # mark job as accepted and done
    with session_scope() as session:
        job = session.query(Job).filter(Job.uuid == job_id).one_or_none()
        if not job:
            log.error('Unable to mark job \'{}\' as done: The Job was not found.'.format(job_id))

            # this is a weird situation, there is no proper way to handle it as this indicates a bug
            # in the Laniakea setup or some other oddity.
            # The least harmful thing to do is to just leave the upload alone and try again later.
            return

        job.result = JobResult.SUCCESS if job_success else JobResult.FAILURE
        job.latest_log_excerpt = None

        # move the log file and Firehose reports to the log storage
        log_target_dir = os.path.join(conf.log_storage_dir, get_dir_shorthand_for_uuid(job_id))
        firehose_target_dir = os.path.join(log_target_dir, 'firehose')
        for fname in dud.get_files():
            if fname.endswith('.log'):
                os.makedirs(log_target_dir, exist_ok=True)

                # move the logfile to its destination and ensure it is named correctly
                target_fname = os.path.join(log_target_dir, job_id + '.log')
                safe_rename(fname, target_fname)
            elif fname.endswith('.firehose.xml'):
                os.makedirs(firehose_target_dir, exist_ok=True)

                # move the firehose report to its own directory and rename it
                fh_target_fname = os.path.join(firehose_target_dir, job_id + '.firehose.xml')
                safe_rename(fname, fh_target_fname)

        # handle different job data
        if job.module == LkModule.ISOTOPE:
            from .import_isotope import handle_isotope_upload

            handle_isotope_upload(
                session, success=job_success, conf=conf, dud=dud, job=job, event_emitter=event_emitter
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
                if job_success:
                    event_emitter.submit_event_for_mod(LkModule.ARCHIVE, 'package-build-success', event_data)
                else:
                    event_emitter.submit_event_for_mod(LkModule.ARCHIVE, 'package-build-failed', event_data)
        else:
            event_emitter.submit_event('upload-accepted', {'job_id': job_id, 'job_failed': not job_success})

    # remove the upload description file from incoming
    os.remove(dud.get_dud_file())

    log.info('Upload {} accepted.'.format(dud.get_filename()))


def reject_upload(conf, dud, reason='Unknown', event_emitter=None):
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

    log.info('Upload {} rejected.'.format(dud.get_filename()))
    if event_emitter:
        event_emitter.submit_event('upload-rejected', {'dud_filename': dud.get_filename(), 'reason': reason})


def import_files_from(conf, incoming_dir):
    '''
    Import files from an untrusted incoming source.

    IMPORTANT: We assume that the uploader can not edit their files post-upload.
    If they could, we would be vulnerable to timing attacks here.
    '''

    emitter = EventEmitter(LkModule.RUBICON)
    for dud_file in glob(os.path.join(incoming_dir, '*.dud')):
        dud = Dud(dud_file)

        try:
            dud.validate(keyrings=conf.trusted_gpg_keyrings)
        except Exception as e:
            reason = 'Signature validation failed: {}'.format(str(e))
            reject_upload(conf, dud, reason, emitter)
            continue

        # if we are here, the file is good to go
        accept_upload(conf, dud, emitter)


def import_files(options):
    conf = RubiConfig()

    if not options.incoming_dir:
        print('No incoming directory set. Can not process any files.')
        sys.exit(1)

    import_files_from(conf, options.incoming_dir)
