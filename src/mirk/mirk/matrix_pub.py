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

import sys
import zmq
import json
import logging as log
from laniakea.msgstream import create_event_listen_socket
from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError
from .config import MirkConfig


message_templates = {'_lk.job.package-build-success':
                     'Package build for <b>{pkgname} {version}</b> was <font color="#265500">successful</font>.',

                     '_lk.job.package-build-failed':
                     'Package build for <b>{pkgname} {version}</b> has <font color="#b7241b">failed</font>.'}


class MatrixPublisher:
    '''
    Publish messages from the Laniakea Message Stream in Matrix rooms.
    '''

    def __init__(self):
        self._zctx = zmq.Context()
        self._lhsub_socket = create_event_listen_socket(self._zctx)
        self._mconf = MirkConfig()
        self._mconf.load()

    def _on_room_message(self, room, event):
        pass

    def _on_event_received(self, event):
        tag = event['tag']
        data = event['data']

        text = ''
        templ = message_templates.get(tag)
        if templ:
            text = templ.format(**data)
        else:
            text = 'Received event type <code>{}</code> with data <code>{}</code>'.format(tag, str(data))

        self._rooms_publish_text(text)

    def _rooms_publish_text(self, text):
        for room in self._rooms:
            room.send_html(text)

    def run(self):
        client = MatrixClient(self._mconf.host)

        try:
            log.debug('Logging into Matrix')
            client.login_with_password(self._mconf.username, self._mconf.password)
        except MatrixRequestError as e:
            if e.code == 403:
                log.error('Bad username or password: {}'.format(str(e)))
                sys.exit(2)
            else:
                log.error('Could not log in - check the server details are correct: {}'.format(str(e)))
                sys.exit(2)
        except Exception as e:
            log.error('Error while logging in: {}'.format(str(e)))
            sys.exit(2)

        log.debug('Joining rooms')
        self._rooms = []
        for room_id in self._mconf.rooms:
            try:
                room = client.join_room(room_id)
            except MatrixRequestError as e:
                if e.code == 400:
                    log.error('Room ID/Alias ("{}") in the wrong format. Can not join room: {}'.format(room_id, str(e)))
                    sys.exit(2)
                else:
                    log.error('Could not find room "{}"'.format(room_id))
                    sys.exit(2)

            room.add_listener(self._on_room_message)
            self._rooms.append(room)

        log.info('Logged into Matrix, ready to publish information')
        client.start_listener_thread()

        while True:
            topic, msg_b = self._lhsub_socket.recv_multipart()
            # TODO: Validate signature here!
            event = json.loads(str(msg_b, 'utf-8'))
            self._on_event_received(event)
