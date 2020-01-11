# -*- coding: utf-8 -*-
#
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
import zmq
import json
import logging as log
from laniakea.utils import json_compact_dump
from zmq.eventloop import ioloop, zmqstream
from laniakea.msgstream import verify_event_message, event_message_is_valid_and_signed
from laniakea.msgstream.signedjson import sign_json


class EventsReceiver:
    '''
    Lighthouse module handling event stream submissions,
    registering them and publishing them to the world.
    '''

    def __init__(self, endpoint, pub_queue):
        from glob import glob
        from laniakea import LocalConfig, LkModule
        from laniakea.msgstream import keyfile_read_verify_key
        from laniakea.msgstream.signing import NACL_ED25519, decode_signing_key_base64, \
            keyfile_read_signing_key

        lconf = LocalConfig()

        self._socket = None
        self._ctx = zmq.Context.instance()

        self._pub_queue = pub_queue
        self._endpoint = endpoint

        # load our own signing key, so we can sign outgoing messages
        keyfile = lconf.secret_curve_keyfile_for_module(LkModule.LIGHTHOUSE)

        self._signer_id = None
        self._signing_key = None
        if os.path.isfile(keyfile):
            self._signer_id, self._signing_key = keyfile_read_signing_key(keyfile)

        if not self._signing_key:
            log.warning('Can not sign outgoing messages: No valid signing key found for this module.')
        else:
            if type(self._signing_key) is str:
                self._signing_key = decode_signing_key_base64(NACL_ED25519, self._signing_key)

        # Load all the keys that we trust to receive messages from
        # TODO: Implement auto-reloading of valid keys list if directory changes
        self._trusted_keys = {}
        for keyfname in glob(os.path.join(lconf.trusted_curve_keys_dir, '*')):
            signer_id, verify_key = keyfile_read_verify_key(keyfname)
            if signer_id and verify_key:
                self._trusted_keys[signer_id] = verify_key

    def _sign_message(self, event):
        ''' Sign an outgoing message, if possible '''

        if not self._signing_key:
            return event

        return sign_json(event, self._signer_id, self._signing_key)

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

        # sign outgoing event, trusted message with our key
        event = self._sign_message(event)
        new_data = json_compact_dump(event)

        # now publish the event to the world
        self._pub_queue.put([bytes(event['tag'], 'utf-8'),
                             bytes(new_data, 'utf-8')])

    def run(self):
        if self._socket:
            log.warning('Tried to run an already running event receiver again.')
            return

        self._socket = self._ctx.socket(zmq.ROUTER)
        self._socket.bind(self._endpoint)

        server_stream = zmqstream.ZMQStream(self._socket)
        server_stream.on_recv_stream(self._event_message_received)

        ioloop.IOLoop.instance().start()
