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
import json
import uuid
import logging as log
from datetime import datetime
from laniakea.db import LkModule, session_factory, config_get_value, \
    Job, JobStatus, JobKind, SparkWorker


class JobWorker:
    '''
    Lighthouse class that handles job requests and distributes tasks.
    '''

    def __init__(self):
        self._session = session_factory()
        self._arch_indep_affinity = config_get_value(LkModule.ARIADNE, 'indep_arch_affinity')


    def _error_reply(self, message):
        return json.dumps({'error': message})

    def _assign_suitable_job(self, job_kind, arch, client_id):
        qres = self._session.execute('''WITH cte AS (
                                        SELECT uuid
                                        FROM   jobs
                                        WHERE  status=:jstatus_old
                                        AND (architecture=:arch OR architecture='any')
                                        AND kind=:jkind
                                        ORDER BY priority, time_created DESC
                                        LIMIT 1
                                        FOR UPDATE
                                        )
                                    UPDATE jobs j SET
                                        status=:jstatus_new,
                                        worker=:worker_id,
                                        time_assigned=now()
                                    FROM cte
                                        WHERE  j.uuid = cte.uuid
                                    RETURNING j.*''', {'jstatus_old': 'WAITING',
                                                   'arch': arch,
                                                   'jkind': job_kind,
                                                   'jstatus_new': 'SCHEDULED',
                                                   'worker_id': client_id})
        res = qres.fetchone()
        self._session.commit()
        return res


    def _process_job_request(self, req_data):
        '''
        Read job request and return a job matching the request or
        null in case we couldn't find any job.
        '''

        client_name = req_data.get('machine_name')
        client_id = req_data.get('machine_id')
        architectures = req_data.get('architectures', [])

        # update information about this client
        worker = self._session.query(SparkWorker) \
            .filter(SparkWorker.uuid==client_id).one_or_none()

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

            self._session.add(worker)

        worker.last_ping = datetime.utcnow()

        accepted_kinds = req_data.get('accepts', [])
        if type(accepted_kinds) is list:
            worker.accepts = accepted_kinds
        else:
            worker.accepts = [str(accepted_kinds)]
        self._session.commit()

        job_data = None
        for accepted_kind in worker.accepts:
            job_assigned = False
            for arch_name in architectures:
                job = None
                if arch_name == self._arch_indep_affinity:
                    # we can  maybe assign an arch:all job to this machine
                    job = self._assign_suitable_job (accepted_kind, 'all', worker.uuid)

                # use the first job with a matching architecture/kind if we didn't find an arch:all job previously
                if not job:
                    job = self._assign_suitable_job (accepted_kind, arch_name, worker.uuid)

                if job:
                    job_data = self._get_job_details(job)
                    job_assigned = True
                    break
            if job_assigned:
                break

        return json.dumps(job_data)


    def process_client_message(self, request):
        '''
        Process the message / request of a Spark worker.
        '''

        req_kind = request.get('request')
        if not req_kind:
            return self._error_reply('Request was malformed.')

        try:
            if req_kind == 'job':
                return self._process_job_request(request)
            if req_kind == 'job-accepted':
                return self._process_job_accepted_request(request)
            if req_kind == 'job-rejected':
                return self._process_job_rejected_request(request)
            if req_kind == 'job-status':
                process_job_status_request(self, request)
                return None
            if req_kind == 'job-success':
                return self._process_job_finished_request(request, True)
            if req_kind == 'job-failed':
                return self._process_job_finished_request(request, False)
            return self._error_reply('Request type is unknown.')
        except Exception as e:
            import traceback
            log.error('Failed to handle request: {} => {}'.format(str(request), str(e)))
            traceback.print_exc()
            return self._error_reply('Failed to handle request: {}'.format(str(e)))

        return None
