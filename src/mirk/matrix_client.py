# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import asyncio
import logging as log
from typing import Optional

from mautrix.types import (
    RoomID,
    EventType,
    Membership,
    MessageType,
    MessageEvent,
    TextMessageEventContent,
)
from mautrix.client import Client as MatrixClient
from mautrix.errors import MLimitExceeded

from .config import MirkConfig


class MirkMatrixClient:
    '''Handle interactions with Matrix for Laniakea's "Mirk" Matrix bot.'''

    def __init__(self, mconf: Optional[MirkConfig] = None):
        self._mconf = mconf
        if not self._mconf:
            self._mconf = MirkConfig()
            self._mconf.load()

        self._joined_rooms: list[str] = []
        self._client = MatrixClient(mxid=self._mconf.username, base_url=self._mconf.host)
        self._client.add_event_handler(EventType.ROOM_MEMBER, self._handle_invite)
        self._client.add_event_handler(EventType.ROOM_MESSAGE, self._handle_message)

    async def _handle_invite(self, event) -> None:
        if event.content.membership == Membership.INVITE:
            await self._client.join_room(event.room_id)

    async def _handle_message(self, event: MessageEvent) -> None:
        if event.sender != self._client.mxid:
            pass  # we don't reply to anything for now

    async def login(self):
        '''Log into Matrix as the currently selected bot user, using password authentication'''
        log.debug('Logging into Matrix')
        await self._client.login(password=self._mconf.password)
        log.info('Logged into Matrix as %s', await self._client.whoami())

        self._joined_rooms = await self._client.get_joined_rooms()
        log.info('Publishing in rooms: %s', ' '.join(self._joined_rooms))

    def stop(self):
        self._client.stop()

    async def send_simple_text(self, room_id: RoomID, text: str):
        '''Publish a simple text message in the selected room.'''
        # pylint: disable=unexpected-keyword-arg
        await self._client.send_message(
            room_id=room_id, content=TextMessageEventContent(msgtype=MessageType.TEXT, body=text)
        )

    async def send_simple_html(self, room_id: RoomID, html: str):
        """Publish a simple HTML message in the selected room."""
        from mautrix.types import Format

        # pylint: disable=unexpected-keyword-arg
        content = TextMessageEventContent(msgtype=MessageType.TEXT)
        content.format = Format.HTML
        content.formatted_body = html

        message_sent = False
        for delay in range(8, 16, 20):
            try:
                await self._client.send_message(room_id=room_id, content=content)
                await asyncio.sleep(0.2)  # we force a delay here to not trigger message limits too quickly
                message_sent = True
                break
            except MLimitExceeded:
                await asyncio.sleep(delay)
        if not message_sent:
            try:
                await self._client.send_message(room_id=room_id, content=content)
            except MLimitExceeded:
                log.error('Message limit exceeded, dropped message: [%s] - %s', str(room_id), content)
