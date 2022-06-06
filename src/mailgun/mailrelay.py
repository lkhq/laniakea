# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import json

import zmq
import zmq.asyncio

from laniakea.logging import log
from laniakea.msgstream import (
    verify_event_message,
    create_event_listen_socket,
    event_message_is_valid_and_signed,
)

from .mailutils import MailSender, MailTemplateLoader


class MailRelay:
    '''
    Publish messages from the Laniakea Message Stream as E-Mail messages.
    '''

    def __init__(self):
        from glob import glob

        from laniakea.msgstream import keyfile_read_verify_key
        from laniakea.localconfig import LocalConfig

        self._zctx = zmq.asyncio.Context()
        self._lhsub_socket = create_event_listen_socket(self._zctx)

        # Read all the keys that we trust, to verify messages
        # TODO: Implement auto-reloading of valid keys list if directory changes
        self._trusted_keys = {}
        for keyfname in glob(os.path.join(LocalConfig().trusted_curve_keys_dir, '*')):
            signer_id, verify_key = keyfile_read_verify_key(keyfname)
            if signer_id and verify_key:
                self._trusted_keys[signer_id] = verify_key

        self._mail_sender = MailSender()
        self._mtmpl = MailTemplateLoader()

        # set of tags that we will actually send emails for
        self._handled_tags = set(())

    async def _send_mail_for(self, tag, data):
        pass  # TODO

    async def _on_event_received(self, event):
        tag = event['tag']
        data = event['data']

        if tag not in self._handled_tags:
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
                break

            # if we are here, we verified one signature without issues and can go forward
            signature_trusted = True
            break

        if not signature_trusted:
            log.warning('Unable to verify signature on event: {}'.format(str(event)))
            return

        await self._send_mail_for(tag, data)

    def stop(self):
        self._running = False

    async def run(self):
        """Run E-Mail relay operations, forever."""

        while self._running:
            mparts = await self._lhsub_socket.recv_multipart()
            if len(mparts) != 2:
                log.info('Received message with odd length: %s', len(mparts))
            msg_b = mparts[1]
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
                log.debug('Invalid message ignored.')
                continue

            await self._on_event_received(event)
