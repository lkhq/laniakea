# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import json

import zmq
import pytest

import laniakea.typing as T
from laniakea.db import Job, JobKind, SourcePackage, session_scope

dataimport_suite = 'unstable'


class TestLighthouseJobRequests:
    @pytest.fixture(autouse=True)
    def setup(self, localconfig, make_curve_trusted_key, lighthouse_server, import_sample_packages, database):
        from laniakea.db import LkModule

        self._client_key = make_curve_trusted_key('spark-builder')
        self._server_key = localconfig.secret_curve_keyfile_for_module(LkModule.LIGHTHOUSE)

        self._base_req = {}
        self._base_req['machine_name'] = 'testmachine'
        self._base_req['machine_id'] = 'a38fe3a8-f2fa-56af-a171-d1b7b6987e6d'

        # Launch server process
        lighthouse_server.start()

        # create jobs
        with session_scope() as session:
            spkg = (
                session.query(SourcePackage).filter(SourcePackage.uuid == 'a1b522ed-4105-59e1-a4da-e4eedd002d6c').one()
            )
            job = Job()
            job.module = LkModule.ARIADNE
            job.kind = JobKind.PACKAGE_BUILD
            job.version = spkg.version
            job.architecture = 'amd64'
            job.trigger = spkg.source_uuid
            job.data = {'suite': 'unstable'}
            session.add(job)

            spkg = (
                session.query(SourcePackage).filter(SourcePackage.uuid == '96d38158-13fb-5be4-b16c-c6d63af13e70').one()
            )
            job = Job()
            job.module = LkModule.ARIADNE
            job.kind = JobKind.PACKAGE_BUILD
            job.version = spkg.version
            job.architecture = 'amd64'
            job.trigger = spkg.source_uuid
            job.data = {'suite': 'unstable'}
            session.add(job)

        yield

    def req_base(self) -> T.Dict[str, T.Any]:
        return self._base_req.copy()

    def send_request(self, sock, req):
        poller = zmq.Poller()
        poller.register(sock, zmq.POLLIN)

        sock.send_string(str(json.dumps(req)))

        # wait for a reply
        reply_msgs = None
        if poller.poll(10000):
            reply_msgs = sock.recv_multipart()
        else:
            pytest.fail('Request expired (Lighthouse server might be unreachable).')
        assert reply_msgs

        reply_raw = reply_msgs[0]
        reply = json.loads(str(reply_raw, 'utf-8'))

        return reply

    def test_request_archive_info(self, new_zmq_curve_socket, localconfig):
        sock = new_zmq_curve_socket(zmq.REQ, localconfig.lighthouse.servers_jobs[0], self._server_key, self._client_key)

        req = self.req_base()
        req['request'] = 'archive-info'

        # request data
        reply = self.send_request(sock, req)
        assert reply == {
            'archive_repos': {
                'extra': {'upload_fqdn': 'laniakea.example.org/_upload', 'upload_method': 'https'},
                'master': {'upload_fqdn': 'laniakea.example.org/_upload', 'upload_method': 'https'},
                'master-debug': {'upload_fqdn': 'laniakea.example.org/_upload', 'upload_method': 'https'},
            }
        }

    def test_request_job(self, new_zmq_curve_socket, localconfig):
        sock = new_zmq_curve_socket(zmq.REQ, localconfig.lighthouse.servers_jobs[0], self._server_key, self._client_key)

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
        assert reply['data']['sha256sum']
        del reply['data']['sha256sum']
        assert reply == {
            'architecture': 'amd64',
            'data': {
                'do_indep': False,
                'dsc_url': '#/master/pool/main/p/pkgnew/pkgnew_0.1-3.dsc',
                'maintainer': 'A Maintainer <maint@example.com>',
                'package_name': 'pkgnew',
                'package_version': '0.1-3',
                'suite': 'unstable',
            },
            'kind': 'package-build',
            'module': 'ariadne',
            'repo': 'master',
            'version': '0.1-3',
        }
