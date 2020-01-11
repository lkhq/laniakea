# -*- coding: utf-8 -*-
#
# Copyright (C) 2019-2020 Matthias Klumpp <matthias@tenstral.net>
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
import zmq
import json
import logging as log
from laniakea.msgstream import create_event_listen_socket, verify_event_message, event_message_is_valid_and_signed
from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError
from .config import MirkConfig
from .messages import message_templates


class MatrixPublisher:
    '''
    Publish messages from the Laniakea Message Stream in Matrix rooms.
    '''

    def __init__(self):
        from glob import glob
        from laniakea.localconfig import LocalConfig
        from laniakea.msgstream import keyfile_read_verify_key

        self._zctx = zmq.Context()
        self._lhsub_socket = create_event_listen_socket(self._zctx)
        self._mconf = MirkConfig()
        self._mconf.load()

        # Read all the keys that we trust, to verify messages
        # TODO: Implement auto-reloading of valid keys list if directory changes
        self._trusted_keys = {}
        for keyfname in glob(os.path.join(LocalConfig().trusted_curve_keys_dir, '*')):
            signer_id, verify_key = keyfile_read_verify_key(keyfname)
            if signer_id and verify_key:
                self._trusted_keys[signer_id] = verify_key

    def _tag_data_to_html_message(self, tag, data):
        ''' Convert the JSON message into a nice HTML string for display. '''

        data['url_webswview'] = self._mconf.webswview_url
        data['url_webview'] = self._mconf.webview_url

        text = ''
        templ = message_templates.get(tag)
        if templ:
            if callable(templ):
                text = templ(tag, data)
            else:
                text = templ.format(**data)
        else:
            text = 'Received event type <code>{}</code> with data <code>{}</code>'.format(tag, str(data))

        return text

    def _on_room_message(self, room, event):
        pass

    def _on_event_received(self, event):
        tag = event['tag']
        data = event['data']

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
                break

            # if we are here, we verified a signature without issues, which means
            # the message is legit and we can sign it ourselves and publish it
            signature_trusted = True
            break

        if signature_trusted:
            text = self._tag_data_to_html_message(tag, data)
        else:
            if self._mconf.allow_unsigned:
                text = self._tag_data_to_html_message(tag, data)
                text = '[<font color="#ed1515">VERIFY_FAILED</font>] ' + text
            else:
                log.info('Unable to verify signature on event: {}'.format(str(event)))
                return

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
            msg_s = str(msg_b, 'utf-8', 'replace')

            try:
                event = json.loads(msg_s)
            except json.JSONDecodeError as e:
                # we ignore invalid requests
                log.info('Received invalid JSON message: %s (%s)', msg_s if len(msg_s) > 1 else msg_b, str(e))
                continue

            # check if the message is actually valid and can be processed
            if not event_message_is_valid_and_signed(event):
                # we currently just silently ignore invalid submissions, no need to spam
                # the logs in case some bad actor flood server with spam
                continue

            self._on_event_received(event)
