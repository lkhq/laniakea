# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Matthias Klumpp <matthias@tenstral.net>
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

import pytest
import zmq
import json
from laniakea.db import session_scope, SourcePackage, Job, JobKind


dataimport_suite = 'unstable'


class TestLighthouseJobRequests:

    @pytest.fixture(autouse=True)
    def setup(self, localconfig, make_zcurve_trusted_key, lighthouse_server,
              import_package_data, database):
        from laniakea.db import LkModule

        self._client_key = make_zcurve_trusted_key('spark-builder')
        self._server_key = localconfig.zcurve_secret_keyfile_for_module(LkModule.LIGHTHOUSE)

        self._base_req = {}
        self._base_req['machine_name'] = 'testmachine'
        self._base_req['machine_id'] = 'a38fe3a8-f2fa-56af-a171-d1b7b6987e6d'

        # Launch server process
        lighthouse_server.start()

        # create jobs
        with session_scope() as session:
            spkg = session.query(SourcePackage) \
                .filter(SourcePackage.uuid == '194f1434-af2e-501c-9baa-8474a3ac4bab') \
                .one()
            job = Job()
            job.module = LkModule.ARIADNE
            job.kind = JobKind.PACKAGE_BUILD
            job.version = spkg.version
            job.architecture = 'amd64'
            job.trigger = spkg.source_uuid
            job.data = {'suite': 'unstable'}
            session.add(job)

            spkg = session.query(SourcePackage) \
                .filter(SourcePackage.uuid == 'eb0d4c75-3055-5084-84ad-19f56c40c3ea') \
                .one()
            job = Job()
            job.module = LkModule.ARIADNE
            job.kind = JobKind.PACKAGE_BUILD
            job.version = spkg.version
            job.architecture = 'amd64'
            job.trigger = spkg.source_uuid
            job.data = {'suite': 'unstable'}
            session.add(job)

    def req_base(self):
        return self._base_req.copy()

    def send_request(self, sock, req):
        poller = zmq.Poller()
        poller.register(sock, zmq.POLLIN)

        sock.send_string(str(json.dumps(req)))

        # wait for a reply
        reply_msgs = None
        if (poller.poll(10000)):
            reply_msgs = sock.recv_multipart()
        else:
            pytest.fail('Request expired (Lighthouse server might be unreachable).')
        assert reply_msgs

        reply_raw = reply_msgs[0]
        reply = json.loads(str(reply_raw, 'utf-8'))

        return reply

    def test_request_job(self, new_zmq_curve_socket, database):
        sock = new_zmq_curve_socket(zmq.DEALER, self._server_key, self._client_key)

        req = self.req_base()
        req['request'] = 'job'
        req['accepts'] = ['none']
        req['architectures'] = ['amd64']

        # request job and fail because we don't accept any
        reply = self.send_request(sock, req)
        assert reply is None

        # request new job
        req['accepts'] = ['package-build']
        reply = self.send_request(sock, req)
        assert reply['time_created']
        del reply['time_created']
        assert reply['uuid']
        del reply['uuid']
        assert reply == {'module': 'ariadne',
                         'kind': 'package-build',
                         'version': '0.0.20-1',
                         'architecture': 'amd64',
                         'data': {'package_name': '0ad',
                                  'package_version': '0.0.20-1',
                                  'maintainer': 'Debian Games Team <pkg-games-devel@lists.alioth.debian.org>',
                                  'suite': 'unstable',
                                  'dsc_url': '#/pool/main/0/0ad/0ad_0.0.20-1.dsc',
                                  'do_indep': False,
                                  'sha256sum': 'f43923ace1c558ad9f9fa88eb3f1764a8c0379013aafbc682a35769449fe8955'}
                         }
