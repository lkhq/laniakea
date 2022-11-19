# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
from typing import Any

import tomlkit

from laniakea import get_config_file


class MirkConfig:
    '''
    Local configuration for mIrk.
    '''

    host = None
    username = None
    password = None
    rooms: dict[str, dict[str, Any]] = {}

    def __init__(self):
        self._loaded = False

        # try to load default configuration
        self.load()

    def load_from_file(self, fname):
        import tomlkit.items

        cdata = {}
        if os.path.isfile(fname):
            with open(fname) as toml_file:
                cdata = tomlkit.load(toml_file)

        self.host = cdata.get('Host', None)
        if not self.host:
            raise Exception('No "Host" entry in mIrk configuration: We need to know a Matrix server to connect to.')

        self.username = cdata.get('Username', None)
        if not self.username:
            raise Exception(
                'No "Username" entry in mIrk configuration: We need to know a Matrix username to connect as.'
            )

        self.password = cdata.get('Password', None)
        if not self.password:
            raise Exception('No "Password" entry in mIrk configuration: We need to know a password to log into Matrix.')

        self.rooms = cdata.get('Rooms', {})
        if not self.rooms:
            raise Exception('No "Rooms" entry in mIrk configuration: We need at least one registered room.')
        if type(self.rooms) is not tomlkit.items.Table:
            raise Exception(
                '"Rooms" entry in mIrk configuration is no mapping: Needs to be a mapping of room names to settings.'
            )
        self.rooms = dict(self.rooms)

        self.allow_unsigned = cdata.get('AllowUnsigned', False)

        self.webview_url = cdata.get('WebViewUrl', '#')
        self.webswview_url = cdata.get('WebSWViewUrl', '#')

        self.message_prefix = cdata.get('MessagePrefix', '')

        self._loaded = True

    def load(self):
        fname = get_config_file('mirk.toml')
        if fname:
            self.load_from_file(fname)
        else:
            raise Exception('Unable to find Mirk configuration (usually in `/etc/laniakea/mirk.toml`')
