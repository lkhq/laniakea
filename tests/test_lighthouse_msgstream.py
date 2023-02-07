# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import json
from uuid import UUID

import zmq
import pytest

from laniakea.msgstream import (
    create_message_tag,
    create_event_message,
    create_submit_socket,
    submit_event_message,
    verify_event_message,
    create_event_listen_socket,
)


class TestLighthouseMsgStream:
    @pytest.fixture(autouse=True)
    def setup(self, localconfig, lighthouse_server, make_curve_trusted_key):
        from laniakea.db import LkModule
        from laniakea.msgstream import keyfile_read_verify_key, keyfile_read_signing_key

        sender_keyfile = make_curve_trusted_key('test-event-submitter')
        self._server_key_fname = localconfig.secret_curve_keyfile_for_module(LkModule.LIGHTHOUSE)

        sender_id, self._sender_verify_key = keyfile_read_verify_key(sender_keyfile)
        assert sender_id == 'test-event-submitter'
        assert self._sender_verify_key

        sender_id, self._sender_signing_key = keyfile_read_signing_key(sender_keyfile)
        assert sender_id == 'test-event-submitter'
        assert self._sender_signing_key

        self._sender_id = sender_id

        self._zctx = zmq.Context()

        # Launch server process
        lighthouse_server.start()

    def test_msg_creation(self):
        '''
        Test creation of new signed messages and check them for validity.
        '''
        from laniakea.db import LkModule

        assert create_message_tag(LkModule.ARCHIVE, 'new-source-packages') == '_lk.archive.new-source-packages'

        m = create_event_message(self._sender_id, '_lk.testsuite.dummy', {'aaa': 'bbb'}, self._sender_signing_key)
        assert m['tag'] == '_lk.testsuite.dummy'
        assert m['format'] == '1.0'
        assert UUID(m['uuid']).version == 1
        assert m['data'] == {'aaa': 'bbb'}

        sigs = m['signatures']
        assert sigs
        assert len(sigs[self._sender_id]['ed25519:0']) > 80

        # this function will throw on error and thereby cause a test failure
        verify_event_message(self._sender_id, m, self._sender_verify_key)

    def test_msg_simple_submit_listen(self):
        # create subscriber socket that is listening to all events emitted by the Lighthouse instance
        sub_socket = create_event_listen_socket(self._zctx)

        # create connection with the Lighthouse server to submit new events
        pub_socket = create_submit_socket(self._zctx)

        submit_event_message(
            pub_socket, self._sender_id, '_lk.testsuite.my-event', {'hello': 'world'}, self._sender_signing_key
        )

        for i in range(1, 4):
            try:
                mparts = sub_socket.recv_multipart()
                break
            except zmq.error.Again as e:
                # the test might be slow, so we retry to get a connection three times
                # before we give up
                sub_socket.close()
                sub_socket = create_event_listen_socket(self._zctx)
                if i == 3:
                    raise e

        assert len(mparts) == 2
        topic = mparts[0]  # pylint: disable=unsubscriptable-object
        msg_b = mparts[1]  # pylint: disable=unsubscriptable-object
        assert topic == b'_lk.testsuite.my-event'

        msg = json.loads(msg_b)
        assert msg['tag'] == '_lk.testsuite.my-event'
        assert msg['format'] == '1.0'
        assert UUID(msg['uuid']).version == 1
        assert msg['data'] == {'hello': 'world'}

        sigs = msg['signatures']
        assert sigs
        assert len(sigs[self._sender_id]['ed25519:0']) > 80
