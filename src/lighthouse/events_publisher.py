# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import zmq
import logging as log
from laniakea.utils import json_compact_dump
from laniakea.msgstream.signedjson import sign_json


class EventsPublisher:
    '''
    Lighthouse helper which handles the actual event publishing from multiple
    receiver processes.
    '''

    def __init__(self, endpoints, pub_queue):
        from laniakea import LocalConfig, LkModule
        from laniakea.msgstream.signing import NACL_ED25519, decode_signing_key_base64, \
            keyfile_read_signing_key

        lconf = LocalConfig()
        self._sockets = []
        self._endpoints = endpoints
        self._ctx = zmq.Context.instance()
        self._pub_queue = pub_queue

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

    def _sign_message(self, event):
        ''' Sign an outgoing message, if possible '''

        if not self._signing_key:
            return event

        return sign_json(event, self._signer_id, self._signing_key)

    def _publish_event(self, event):
        # sign outgoing trusted message with our key
        # anything that is in this queue has already been
        # checked and is trusted
        event = self._sign_message(event)
        new_data = json_compact_dump(event)

        # create message
        msg = [bytes(event['tag'], 'utf-8'),
               bytes(new_data, 'utf-8')]

        # send message
        for socket in self._sockets:
            try:
                socket.send_multipart(msg)
            except Exception as e:
                log.warning('Unable to publish event: {} (data was: {})'.format(str(e), str(msg)))

    def run(self):
        if self._sockets:
            log.warning('Tried to run an already running event publisher again.')
            return

        for endpoint in self._endpoints:
            socket = self._ctx.socket(zmq.PUB)
            socket.bind(endpoint)
            self._sockets.append(socket)

        while True:
            event = self._pub_queue.get()
            self._publish_event(event)
