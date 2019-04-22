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
import logging as log
from laniakea import LocalConfig, LkModule
from lighthouse.worker import JobWorker

import zmq
import zmq.auth
from zmq.auth.ioloop import IOLoopAuthenticator
from zmq.eventloop import ioloop, zmqstream


class LhServer:
    '''
    Lighthouse Server
    '''

    def __init__(self, verbose=False):
        self._server = None
        self._ctx = zmq.Context.instance()

        if verbose:
            log.basicConfig(level=log.DEBUG, format="[%(levelname)s] %(message)s")

        lconf = LocalConfig()
        self._trusted_keys_dir = lconf.zcurve_trusted_certs_dir + '/'
        self._server_private_key = lconf.zcurve_secret_keyfile_for_module(LkModule.LIGHTHOUSE)

        self._jobs_endpoint = lconf.lighthouse_endpoint
        self._worker = JobWorker()

    def _client_request_received(self, server, msg):
        try:
            request = json.loads(msg[1])
        except json.JSONDecodeError as e:
            # we ignore invalid requests
            log.info('Received invalid JSON request from client: %s (%s)', msg, str(e))
            return

        try:
            reply = self._worker.process_client_message(request)
        except Exception as e:
            reply = json.dumps({'error': 'Internal Error: {}'.format(e)})

        # an empty result is assumed to mean everything went fine
        if not reply:
            reply = json.dumps(None)

        reply_msg = [msg[0], reply.encode('utf-8')]

        log.debug('Sending %s', reply_msg)
        server.send_multipart(reply_msg)

    def _setup_server(self):
        '''
        Set up the server with authentication.
        '''
        self._server = self._ctx.socket(zmq.ROUTER)

        server_public, server_secret = zmq.auth.load_certificate(self._server_private_key)
        self._server.curve_secretkey = server_secret
        self._server.curve_publickey = server_public
        self._server.curve_server = True  # must come before bind
        self._server.bind(self._jobs_endpoint)

        server_stream = zmqstream.ZMQStream(self._server)
        server_stream.on_recv_stream(self._client_request_received)

    def run(self):
        if self._server:
            log.warning('Tried to run an already running server again.')
            return

        if not os.path.isfile(self._server_private_key):
            log.critical('No private key is installed for Lighthouse. Can not create an encrypted connection.')
            sys.exit(2)

        if not os.path.isdir(self._trusted_keys_dir):
            log.warning('Trusted keys directory does not exist. No clients will be able to make connections to this Lighthouse server.')

        # Start an authenticator for this context.
        auth = IOLoopAuthenticator(self._ctx)
        # NOTE: auth.allow('127.0.0.1') can be used to allow access only from specific IPs (whitelisting)

        # Tell authenticator to use the certificate in a directory
        auth.configure_curve(domain='*', location=self._trusted_keys_dir)

        self._setup_server()

        auth.start()
        ioloop.IOLoop.instance().start()
