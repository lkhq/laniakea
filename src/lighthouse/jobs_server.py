# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import sys
import json
import logging as log

import zmq
import zmq.auth
from zmq.eventloop import ioloop, zmqstream
from zmq.auth.ioloop import IOLoopAuthenticator

from laniakea import LkModule, LocalConfig
from laniakea.utils import json_compact_dump
from lighthouse.jobs_worker import JobWorker


class JobsServer:
    '''
    Lighthouse module serving job requests.
    '''

    def __init__(self, endpoint, pub_queue):
        self._server = None
        self._ctx = zmq.Context.instance()

        lconf = LocalConfig()
        self._trusted_keys_dir = lconf.trusted_curve_keys_dir + '/'
        self._server_private_key = lconf.secret_curve_keyfile_for_module(LkModule.LIGHTHOUSE)

        self._jobs_endpoint = endpoint
        self._worker = JobWorker(pub_queue)

    def _client_request_received(self, server, msg):
        '''Called when we receive a request from a client.'''

        if len(msg) != 3:
            log.info('Received request of invalid length %s: %s', str(len(msg)), msg)
            return
        address, _, data = msg

        try:
            request = json.loads(data)
        except json.JSONDecodeError as e:
            # we ignore invalid requests
            log.info('Received invalid JSON request from client: %s (%s)', msg, str(e))
            return

        try:
            reply = self._worker.process_client_message(request)
        except Exception as e:
            reply = json_compact_dump({'error': 'Internal Error: {}'.format(e)}, as_bytes=True)

        # an empty result means we will send an empty message back, as ACK for the REQ connection
        if not reply:
            reply = b''

        # ensure we have the bytes of a JSON string
        # (workers are permitted to return e.g. True or UTF-8 strings)
        if type(reply) is str:
            reply = reply.encode('utf-8')
        elif type(reply) is not bytes:
            reply = json_compact_dump(reply, as_bytes=True)

        reply_msg = [address, b'', reply]

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
            log.warning(
                'Trusted keys directory does not exist. No clients will be able to make connections to this Lighthouse server.'
            )

        # Start an authenticator for this context.
        auth = IOLoopAuthenticator(self._ctx)
        # NOTE: auth.allow('127.0.0.1') can be used to allow access only from specific IPs (whitelisting)

        # Tell authenticator to use the certificate in a directory
        auth.configure_curve(domain='*', location=self._trusted_keys_dir)

        self._setup_server()

        auth.start()
        ioloop.IOLoop.instance().start()
