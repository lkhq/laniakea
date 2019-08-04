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
from datetime import datetime
from laniakea.msgstream.signing import NACL_ED25519, decode_signing_key_base64, decode_verify_key_bytes
from laniakea.msgstream.signedjson import sign_json, verify_signed_json
from laniakea.utils import decode_base64


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
