# Copyright (C) 2018-2019 Matthias Klumpp <matthias@tenstral.net>
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
import logging as log
from glob import glob
from laniakea.dud import Dud
from laniakea.utils import get_dir_shorthand_for_uuid, random_string
from laniakea.db import session_scope, Job, JobStatus, JobKind, JobResult
from .rubiconfig import RubiConfig
from .utils import safe_rename


def accept_upload(conf, dud):
    '''
    Accept the upload and move its data to the right places.
    '''

    job_success = dud.get('X-Spark-Success') == 'Yes'
    job_id = dud.get('X-Spark-Job')

    # mark job as accepted and done
    with session_scope() as session:
        job = session.query(Job).filter(Job.uuid==job_id).one_or_none()
        if not job:
            log.error('Unable to mark job \'{}\' as done: The Job was not found.'.format(job_id))

            # this is a weird situation, there is no proper way to handle it as this indicates a bug
            # in the Laniakea setup or some other oddity.
            # The least harmful thing to do is to just leave the upload alone and try again later.
            return

        job.result = JobResult.SUCCESS if job_success else JobResult.FAILURE

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

        # some modules get special treatment
        if job_success:
            from .import_isotope import handle_isotope_upload

            if job.module == LkModule.ISOTOPE:
                handle_isotope_upload(session, conf, dud, job)

    # remove the upload description file from incoming
    os.remove(dud.get_dud_file())
    log.info("Upload {} accepted.",  dud.get_filename());


def reject_upload(conf, dud, reason='Unknown'):
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

    log.info('Upload {} rejected.', dud.get_filename())


def import_files_from(conf, incoming_dir):
    '''
    Import files from an untrusted incoming source.

    IMPORTANT: We assume that the uploader can not edit their files post-upload.
    If they could, we would be vulnerable to timing attacks here.
    '''

    for dud_file in glob(os.path.join(incoming_dir, '*.dud')):
        dud = Dud(dud_file)

        try:
            dud.validate(keyrings=conf.trusted_gpg_keyrings)
        except Exception as e:
            reason = 'Signature validation failed: {}'.format(str(e))
            reject_upload(conf, dud, reason)
            continue

        # if we are here, the file is good to go
        accept_upload(conf, dud)


def import_files(options):
    conf = RubiConfig()

    if not options.incoming_dir:
        print('No incoming directory set. Can not process any files.')
        sys.exit(1)

    import_files_from(conf, options.incoming_dir)
