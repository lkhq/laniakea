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
import uuid
import random
import zmq
from datetime import datetime
from laniakea.msgstream.signing import NACL_ED25519, decode_signing_key_base64, decode_verify_key_bytes, \
    keyfile_read_signing_key
from laniakea.msgstream.signedjson import sign_json, verify_signed_json
from laniakea.utils import decode_base64, json_compact_dump
from laniakea.localconfig import LocalConfig
from laniakea.logging import log


def create_message_tag(module, subject):
    '''
    Create a message type tag for internal Laniakea modules.
    '''
    return '_lk.{}.{}'.format(module, subject)


def create_event_message(sender, tag, data, key):
    '''
    Create and sign a new event message to send to a Laniakea Lighthouse
    instance for publication.
    '''

    if type(key) is str:
        key = decode_signing_key_base64(NACL_ED25519, key)

    msg = {'tag': tag,
           'uuid': str(uuid.uuid1()),
           'format': '1.0',
           'time': datetime.now().isoformat(),
           'data': data}

    return sign_json(msg, sender, key)


def event_message_is_valid_and_signed(event):
    '''
    Check if an event message is valid and has signatures attached.
    '''
    if 'tag' not in event:
        return False
    if 'uuid' not in event:
        return False
    if 'format' not in event:
        return False
    if 'time' not in event:
        return False
    if 'data' not in event:
        return False

    signatures = event.get('signatures')
    if len(signatures) < 1:
        return False
    return True


def verify_event_message(sender, event, key, assume_valid=False):
    '''
    Verify the validity of this event, via its required fields as
    well as cryptographical signature.
    '''
    if not assume_valid:
        if not event_message_is_valid_and_signed(event):
            raise Exception('Message was not valid or not signed.')

    if type(key) is str:
        key = decode_verify_key_bytes(NACL_ED25519 + ':' + '0', decode_base64(key))

    verify_signed_json(event, sender, key)  # this will raise an error if validation fails


def create_submit_socket(zmq_context):
    '''
    Create a ZeroMQ socket that is connected to a Lighthouse instance in order
    to submit messages to it.
    '''

    lconf = LocalConfig()
    servers = lconf.lighthouse.servers_submit
    if not servers:
        return  # we can't send events, as there are no Lighthouse instances registered

    submit_server = random.choice(servers)

    socket = zmq_context.socket(zmq.DEALER)
    socket.connect(submit_server)

    return socket


def submit_event_message(socket, sender, tag, data, key):
    '''
    Create a new event message, sign it and send it via the specified socket.
    '''
    if not socket:
        return  # don't send the message if we do not have a valid socket
    msg = create_event_message(sender, tag, data, key)
    socket.send_string(json_compact_dump(msg))


def create_event_listen_socket(zmq_context, subscribed_tags=[]):
    '''
    Create a ZeroMQ socket that is listening to events published on a
    Lighthouse event publisher socket.
    '''

    lconf = LocalConfig()
    publish_server = random.choice(lconf.lighthouse.servers_publish)

    socket = zmq_context.socket(zmq.SUB)
    socket.connect(publish_server)

    if not subscribed_tags:
        socket.setsockopt_string(zmq.SUBSCRIBE, '')
    else:
        for tag in subscribed_tags:
            socket.setsockopt_string(zmq.SUBSCRIBE, tag)

    return socket


class EventEmitter:
    '''
    Emit events on the Laniakea Message Stream if the system
    is configured to do so.
    Otherwise do nothing.
    '''

    def __init__(self, module):
        self._module = str(module)
        lconf = LocalConfig()
        keyfile = lconf.secret_curve_keyfile_for_module(self._module)

        self._zctx = zmq.Context()
        self._socket = create_submit_socket(self._zctx)

        signer_id = None
        signing_key = None
        if os.path.isfile(keyfile):
            signer_id, signing_key = keyfile_read_signing_key(keyfile)

        if self._socket and not signing_key:
            log.warning('Can not publish events: No valid signing key found for this module.')
            self._socket = None
        self._signer_id = signer_id
        self._signing_key = signing_key

    def submit_event(self, subject, data):
        '''
        Submit an event to a Lighthouse instance for publication.
        '''
        tag = create_message_tag(self._module, subject)
        submit_event_message(self._socket,
                             self._signer_id,
                             tag,
                             data,
                             self._signing_key)

    def submit_event_for_mod(self, mod, subject, data):
        '''
        Submit and event for a different module than what the
        :EventEmitter was created for.
        '''
        tag = create_message_tag(mod, subject)
        submit_event_message(self._socket,
                             self._signer_id,
                             tag,
                             data,
                             self._signing_key)

    def submit_event_for_tag(self, tag, data):
        '''
        Submit and event and set a custom tag.
        '''
        submit_event_message(self._socket,
                             self._signer_id,
                             tag,
                             data,
                             self._signing_key)
