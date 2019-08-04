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

import uuid
import random
import zmq
from datetime import datetime
from laniakea.msgstream.signing import NACL_ED25519, decode_signing_key_base64, decode_verify_key_bytes
from laniakea.msgstream.signedjson import sign_json, verify_signed_json
from laniakea.utils import decode_base64, json_compact_dump
from laniakea.localconfig import LocalConfig


def create_message_tag(module, subject):
    '''
    Create a message tyoe tag for internal Laniakea modules.
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
    submit_server = random.choice(lconf.lighthouse.servers_submit)

    socket = zmq_context.socket(zmq.DEALER)
    socket.connect(submit_server)

    return socket


def submit_event_message(socket, sender, tag, data, key):
    '''
    Create a new event message, sign it and send it via the specified socket.
    '''
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
