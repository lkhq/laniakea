# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import uuid
import logging as log
from datetime import datetime

import laniakea.typing as T
from laniakea import LkModule, LocalConfig
from laniakea.db import (
    Job,
    JobKind,
    JobResult,
    JobStatus,
    SparkWorker,
    SourcePackage,
    ImageBuildRecipe,
    ArchiveRepoSuiteSettings,
    session_scope,
    config_get_value,
)
from laniakea.utils import json_compact_dump
from laniakea.msgstream import create_message_tag


class JobWorker:
    '''
    Lighthouse class that handles job requests and distributes tasks.
    '''

    def __init__(self, event_pub_queue):
        self._lconf = LocalConfig()
        self._arch_indep_affinity = config_get_value(LkModule.ARIADNE, 'indep_arch_affinity')
        self._event_pub_queue = event_pub_queue

        with session_scope() as session:
            # FIXME: We need much better ways to select the right suite to synchronize with
            incoming_suite = (
                session.query(ArchiveRepoSuiteSettings)
                .filter(ArchiveRepoSuiteSettings.accept_uploads == True)  # noqa: E712
                .filter(ArchiveRepoSuiteSettings.repo.has(name=self._lconf.master_repo_name))
                .order_by(ArchiveRepoSuiteSettings.suite_id)
                .first()
            ).suite
            self._default_incoming_suite_name = incoming_suite.name

    def _emit_event(self, subject, data):
        if not self._event_pub_queue:
            return  # do nothing if event publishing is disabled

        tag = create_message_tag('jobs', subject)
        msg = {'tag': tag, 'uuid': str(uuid.uuid1()), 'format': '1.0', 'time': datetime.now().isoformat(), 'data': data}
        self._event_pub_queue.put(msg)

    def _error_reply(self, message):
        return json_compact_dump({'error': message})

    def _assign_suitable_job(self, session, job_kind, arch, client_id):
        qres = session.execute(
            '''WITH cte AS (
                                        SELECT uuid
                                        FROM   jobs
                                        WHERE  status=:jstatus_old
                                        AND (architecture=:arch OR architecture='any')
                                        AND kind=:jkind
                                        ORDER BY priority, time_created
                                        LIMIT 1
                                        FOR UPDATE
                                        )
                                    UPDATE jobs j SET
                                        status=:jstatus_new,
                                        worker=:worker_id,
                                        time_assigned=now()
                                    FROM cte
                                        WHERE  j.uuid = cte.uuid
                                    RETURNING j.*''',
            {
                'jstatus_old': 'WAITING',
                'arch': arch,
                'jkind': job_kind,
                'jstatus_new': 'SCHEDULED',
                'worker_id': client_id,
            },
        )
        res = qres.fetchone()
        session.commit()
        return res

    def _get_job_details(self, session, job_dict) -> dict[str, T.Any] | None:
        '''
        Retrieve additional information about a given job.
        '''

        job_kind = job_dict['kind']
        job_uuid_str = str(job_dict['uuid'])
        trigger_uuid = job_dict['trigger']
        job_version = job_dict['version']

        job = session.query(Job).filter(Job.uuid == job_uuid_str).one()

        info: dict[str, T.Any] = {}
        jdata: dict[str, T.Any] = {}
        info['uuid'] = job_uuid_str
        info['module'] = job_dict['module']
        info['kind'] = job_kind
        info['version'] = job_version
        info['architecture'] = job_dict['architecture']
        info['time_created'] = job.time_created.isoformat()

        if job_kind == JobKind.PACKAGE_BUILD:
            # Sanity check for broken configuration (archive URL is not mandatory (yet))
            if not self._lconf.archive_url:
                log.error(
                    'Trying to schedule a package build job, but archive URL is not set in local config. Please fix your configuration!'
                )
                job.status = JobStatus.WAITING
                session.commit()

                # This is a server error, no need to inform the client about it as well
                return None

            spkg: SourcePackage | None = (
                session.query(SourcePackage)
                .filter(SourcePackage.source_uuid == trigger_uuid)
                .filter(SourcePackage.version == job_version)
                .one_or_none()
            )
            if not spkg:
                job.status = JobStatus.TERMINATED
                job.latest_log_excerpt = (
                    'We were unable to find a source package for this build job. The job has been terminated.'
                )
                session.commit()

                # This not an error the client needs to know about
                return None

            if not job.data:
                job.status = JobStatus.TERMINATED
                job.latest_log_excerpt = (
                    'Required data was missing to perform this job. This is an internal server error.'
                )
                session.commit()

                # This not an error the client needs to know about
                return None

            if job.suite:
                suite_target_name = job.suite.name
            else:
                suite_target_name = self._default_incoming_suite_name

            jdata['package_name'] = spkg.name
            jdata['package_version'] = spkg.version
            jdata['maintainer'] = spkg.maintainer
            jdata['repo'] = spkg.repo.name
            jdata['suite'] = suite_target_name
            jdata['dsc_url'] = None

            # determine if we should do arch-indep builds, if that's not already enforced
            jdata['do_indep'] = job.data.get('do_indep', False)
            if not jdata['do_indep']:
                if job.architecture == self._arch_indep_affinity or job.architecture == 'all':
                    jdata['do_indep'] = True

            # for arch:all jobs, we cheat and set the arch affinity as the actual architecture this job will be running on,
            # since nothing can be built on an arch:all chroot
            if job.architecture == 'all':
                info['architecture'] = self._arch_indep_affinity

            # FIXME: Fetch the archive URL from the repository database entry
            for f in spkg.files:
                if not f.fname.endswith('.dsc'):
                    continue
                jdata['dsc_url'] = self._lconf.archive_url + '/' + f.fname
                jdata['sha256sum'] = f.sha256sum
                break

            if not jdata['dsc_url']:
                job.status = JobStatus.TERMINATED
                job.latest_log_excerpt = (
                    'We were unable to find a source package .dsc file for this build. The job has been terminated.'
                )
                session.commit()

                # This not an error the client needs to know about
                return None
        elif job_kind == JobKind.OS_IMAGE_BUILD:
            recipe: ImageBuildRecipe | None = (
                session.query(ImageBuildRecipe).filter(ImageBuildRecipe.uuid == trigger_uuid).one_or_none()
            )
            if not recipe:
                job.status = JobStatus.TERMINATED
                job.latest_log_excerpt = (
                    'We were unable to find the image build recipe for this job. The job has been terminated.'
                )
                session.commit()

                # This not an error the client needs to know about
                return None

            jdata['image_format'] = str(recipe.format)
            jdata['git_url'] = recipe.git_url
            jdata['distribution'] = recipe.distribution
            jdata['suite'] = recipe.suite
            jdata['environment'] = recipe.environment
            jdata['style'] = recipe.style
            jdata['architecture'] = job.data.get('architecture', job.architecture) if job.data else job.architecture

        info['data'] = jdata
        return info

    def _process_job_request(self, session, req_data):
        '''
        Read job request and return a job matching the request or
        null in case we couldn't find any job.
        '''

        client_name = req_data.get('machine_name')
        client_id = req_data.get('machine_id')
        architectures = req_data.get('architectures', [])

        # update information about this client
        worker = session.query(SparkWorker).filter(SparkWorker.uuid == client_id).one_or_none()

        # we might have a new machine, so set the ID again to create an empty new worker
        if not worker:
            worker = SparkWorker()

            # this may throw an exception which is caought and sent back to the worker
            # (the worker then has the oportunity to fix its UUID)
            try:
                worker.uuid = uuid.UUID(client_id)
            except TypeError as e:
                return self._error_reply('Failed to parse client UUID: {}'.format(str(e)))

            worker.name = client_name
            worker.enabled = True

            session.add(worker)

        worker.last_ping = datetime.utcnow()

        accepted_kinds = req_data.get('accepts', [])
        if type(accepted_kinds) is list:
            worker.accepts = accepted_kinds
        else:
            worker.accepts = [str(accepted_kinds)]
        session.commit()

        job_data = None
        job_assigned = False
        for accepted_kind in worker.accepts:
            for arch_name in architectures:
                job = None
                if arch_name == self._arch_indep_affinity:
                    # we can  maybe assign an arch:all job to this machine
                    job = self._assign_suitable_job(session, accepted_kind, 'all', worker.uuid)

                # use the first job with a matching architecture/kind if we didn't find an arch:all job previously
                if not job:
                    job = self._assign_suitable_job(session, accepted_kind, arch_name, worker.uuid)

                if job:
                    job_data = self._get_job_details(session, job)
                    job_assigned = True

                    event_data = {
                        'job_id': job_data['uuid'],
                        'client_name': client_name,
                        'client_id': client_id,
                        'job_module': job_data['module'],
                        'job_kind': job_data['kind'],
                        'job_version': job_data['version'],
                        'job_architecture': job_data['architecture'],
                    }
                    self._emit_event('job-assigned', event_data)
                    break
            if job_assigned:
                break

        return json_compact_dump(job_data)

    def _process_job_accepted_request(self, session, request):
        '''
        If the worker actually accepts a job we sent to it and starts
        working on it, this method is triggered.
        On success, we wend the job back again.
        '''

        job_id = request.get('uuid')
        client_name = request.get('machine_name')
        client_id = request.get('machine_id')

        if not job_id:
            return self._error_reply('Job ID was missing.')
        if not client_name:
            return self._error_reply('Name of the machine making this request was missing.')
        if not client_id:
            return self._error_reply('ID of the machine making this request was missing.')

        job = session.query(Job).filter(Job.uuid == job_id).one_or_none()
        if not job:
            return self._error_reply('Unable to find job with the requested ID.')

        job.status = JobStatus.RUNNING
        session.commit()

        event_data = {'job_id': job_id, 'client_name': client_name, 'client_id': client_id}
        self._emit_event('job-accepted', event_data)

        return True

    def _process_job_rejected_request(self, session, request):
        '''
        If the worker rejects a job that we gave to it (for example because
        it ran out of resources and can't process it), we reset the
        status of the respective job in the database.
        '''

        job_id = request.get('uuid')
        client_name = request.get('machine_name')
        client_id = request.get('machine_id')

        if not job_id:
            return self._error_reply('Job ID was missing.')
        if not client_name:
            return self._error_reply('Name of the machine making this request was missing.')
        if not client_id:
            return self._error_reply('ID of the machine making this request was missing.')

        job = session.query(Job).filter(Job.uuid == job_id).one_or_none()
        if not job:
            return self._error_reply('Unable to find job with the requested ID.')

        if job.status == JobStatus.RUNNING:
            # we also want to allow workers to reject a job that they have already accepted - if the workers
            # change their mind that late, it's usually a sign that something broke. In this case, we don't want
            # to block a possibly important job though, and rather have another worker take it instead.
            # (we do log this behavior though, for now only to the system journal)
            # TODO: Generate a Laniakea event for this behavior
            log.info(
                'Worker "{}" changed its mind on job "{}" and rejected it after it was already running.'.format(
                    client_name, str(job_id)
                )
            )
        elif job.status != JobStatus.SCHEDULED:
            log.warning(
                'Worker "{}" rejected job "{}", but the job was not scheduled (state: {}).'.format(
                    client_name, str(job_id), str(job.status)
                )
            )

        job.status = JobStatus.WAITING
        session.commit()

        event_data = {'job_id': job_id, 'client_name': client_name, 'client_id': client_id}
        self._emit_event('job-rejected', event_data)

        return True

    def _process_job_status_request(self, session, request):
        '''
        When a job is running, the worker will periodically send
        status information, which we collect here.
        '''

        job_id = request.get('uuid')
        client_id = request.get('machine_id')
        log_excerpt = request.get('log_excerpt')

        if not job_id:
            return self._error_reply('Job ID was missing.')
        if not client_id:
            return self._error_reply('ID of the machine making this request was missing.')

        # update log & status data
        if log_excerpt:
            # sometimes nasty builders send NULL characters in the string, protect against that
            log_excerpt = log_excerpt.replace('\x00', '')
            session.query(Job).filter(Job.uuid == job_id).update({'latest_log_excerpt': log_excerpt})

        # update last seen information
        session.query(SparkWorker).filter(SparkWorker.uuid == client_id).update({'last_ping': datetime.utcnow()})
        session.commit()

    def _process_job_finished_request(self, session, request, success: bool):
        """
        Request made when the job has finished and we are expecting results from the worker
        to be uploaded.
        """

        job_id = request.get('uuid')
        client_name = request.get('machine_name')
        client_id = request.get('machine_id')

        if not job_id:
            return self._error_reply('Job ID was missing.')
        if not client_name:
            return self._error_reply('Name of the machine making this request was missing.')
        if not client_id:
            return self._error_reply('ID of the machine making this request was missing.')

        job = session.query(Job).filter(Job.uuid == job_id).one_or_none()
        if not job:
            return self._error_reply('Unable to find job with the requested ID.')

        # we use the maybe values here, as we can only be really sure of success as soon as
        # the worker has uploaded the job artifacts and the responsible Laniakea
        # module has verified them.
        # (if things get lost along the way or fail verification, we may need to restart this job)
        job.result = JobResult.SUCCESS_PENDING if success else JobResult.FAILURE_PENDING
        job.status = JobStatus.DONE

        event_data = {'job_id': job_id, 'client_name': client_name, 'client_id': client_id, 'result': str(job.result)}
        self._emit_event('job-finished', event_data)

        return True

    def process_client_message(self, request):
        '''
        Process the message / request of a Spark worker.
        '''

        req_kind = request.get('request')
        if not req_kind:
            return self._error_reply('Request was malformed.')

        try:
            with session_scope() as session:
                if req_kind == 'job':
                    return self._process_job_request(session, request)
                if req_kind == 'job-accepted':
                    return self._process_job_accepted_request(session, request)
                if req_kind == 'job-rejected':
                    return self._process_job_rejected_request(session, request)
                if req_kind == 'job-status':
                    self._process_job_status_request(session, request)
                    return None  # we don't reply to this
                if req_kind == 'job-success':
                    return self._process_job_finished_request(session, request, True)
                if req_kind == 'job-failed':
                    return self._process_job_finished_request(session, request, False)
                return self._error_reply('Request type is unknown.')
        except Exception as e:
            import traceback

            log.error('Failed to handle request: {} => {}'.format(str(request), str(e)))
            traceback.print_exc()
            return self._error_reply('Failed to handle request: {}'.format(str(e)))

        return None
