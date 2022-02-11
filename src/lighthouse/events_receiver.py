# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import json
import logging as log

import zmq
from zmq.eventloop import ioloop, zmqstream

from laniakea.msgstream import verify_event_message, event_message_is_valid_and_signed


class EventsReceiver:
    '''
    Lighthouse module handling event stream submissions,
    registering them and publishing them to the world.
    '''

    def __init__(self, endpoint, pub_queue):
        from glob import glob

        from laniakea import LocalConfig
        from laniakea.msgstream import keyfile_read_verify_key

        lconf = LocalConfig()
        self._socket = None
        self._ctx = zmq.Context.instance()

        self._pub_queue = pub_queue
        self._endpoint = endpoint

        # Load all the keys that we trust to receive messages from
        # TODO: Implement auto-reloading of valid keys list if directory changes
        self._trusted_keys = {}
        for keyfname in glob(os.path.join(lconf.trusted_curve_keys_dir, '*')):
            signer_id, verify_key = keyfile_read_verify_key(keyfname)
            if signer_id and verify_key:
                self._trusted_keys[signer_id] = verify_key

    def _event_message_received(self, socket, msg):
        data = str(msg[1], 'utf-8', 'replace')
        try:
            event = json.loads(data)
        except json.JSONDecodeError as e:
            # we ignore invalid requests
            log.info('Received invalid JSON message from sender: %s (%s)', data if len(data) > 1 else msg, str(e))
            return

        # check if the message is actually valid and can be processed
        if not event_message_is_valid_and_signed(event):
            # we currently just silently ignore invalid submissions
            return

        signatures = event.get('signatures')
        signature_trusted = False
        for signer in signatures.keys():
            key = self._trusted_keys.get(signer)
            if not key:
                continue
            try:
                verify_event_message(signer, event, key, assume_valid=True)
            except Exception as e:
                log.info('Invalid signature on event ({}): {}'.format(str(e), str(event)))
                return

            # if we are here, we verified a signature without issues, which means
            # the message is legit and we can sign it ourselves and publish it
            signature_trusted = True
            break

        if not signature_trusted:
            log.info('Unable to verify signature on event: {}'.format(str(event)))
            return

        # now publish the event to the world
        self._pub_queue.put(event)

    def run(self):
        if self._socket:
            log.warning('Tried to run an already running event receiver again.')
            return

        self._socket = self._ctx.socket(zmq.ROUTER)
        self._socket.bind(self._endpoint)

        server_stream = zmqstream.ZMQStream(self._socket)
        server_stream.on_recv_stream(self._event_message_received)

        ioloop.IOLoop.instance().start()
