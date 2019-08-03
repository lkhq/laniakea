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

import zmq
import json
import logging as log
from zmq.eventloop import ioloop, zmqstream
from laniakea.signedjson import verify_signed_json


class EventsReceiver:
    '''
    Lighthouse module handling event stream submissions,
    registering them and publishing them to the world.
    '''

    def __init__(self, endpoint, pub_queue):
        self._socket = None
        self._ctx = zmq.Context.instance()

        self._pub_queue = pub_queue
        self._endpoint = endpoint

    def _event_message_received(self, socket, msg):
        try:
            event = json.loads(msg[1])
        except json.JSONDecodeError as e:
            # we ignore invalid requests
            log.info('Received invalid JSON message from sender: %s (%s)', msg[1] if len(msg) > 1 else msg, str(e))
            return

        event_tag = event.get('tag')
        signatures = event.get('signatures')

        # check if the message is actually valid and can be processed
        if not event_tag or not signatures:
            return

        if len(signatures) < 1:
            log.info('Signature missing on message: {}'.format(str(event)))
            return

        signature_checked = False
        for signer in signatures.keys():
            try:
                verify_signed_json(event, signer, 'TODO')  # TODO
            except Exception as e:
                log.info('Invalid signature on event ({}): {}'.format(str(e), str(event)))
                return

        if not signature_checked:
            log.info('Unable to verify signature on event: {}'.format(str(event)))
            return

        # now publish the event to the world
        self._pub_queue.put([bytes(event_tag, 'utf-8'), msg[1]])

    def run(self):
        if self._socket:
            log.warning('Tried to run an already running event receiver again.')
            return

        self._socket = self._ctx.socket(zmq.ROUTER)
        self._socket.bind(self._endpoint)

        server_stream = zmqstream.ZMQStream(self._socket)
        server_stream.on_recv_stream(self._event_message_received)

        ioloop.IOLoop.instance().start()
