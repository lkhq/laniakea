# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os

import tomlkit

import laniakea.typing as T
from laniakea.utils import listify
from laniakea.localconfig import get_config_file


class MailgunConfig:
    """Configuration for the maintenance scheduler daemon."""

    instance = None

    class __MailgunConfig:
        def __init__(self, fname=None):
            if not fname:
                fname = get_config_file('mailgun.toml')
            self.fname = fname

            cdata = {}
            if fname and os.path.isfile(fname):
                with open(fname) as toml_file:
                    cdata = tomlkit.load(toml_file)

            self._mail_origin_address = listify(cdata.get('MyEmailAddress', 'Dummy UNSET <set_me@example.org>'))

            self._sendmail_cmd = cdata.get('SendmailCommand', '/usr/sbin/sendmail -odq -oi -t').split()
            self._mail_whitelist = listify(cdata.get('MailWhitelist', []))
            self._mail_whitelist_files = listify(cdata.get('MailWhitelistFiles', []))

            self._announce_email = cdata.get('AnnounceMailinglist')

        @property
        def mail_origin_address(self) -> str:
            """Mail address that we will send emails from"""
            return self._mail_origin_address

        @property
        def sendmail_cmd(self) -> T.List[str]:
            """Sendmail command line"""
            return self._sendmail_cmd

        @property
        def mail_whitelist(self) -> T.List[str]:
            """Mail whitelist entries"""
            return self._mail_whitelist

        @property
        def mail_whitelist_files(self) -> T.List[T.PathUnion]:
            """List of file paths with mail whitelist entries"""
            return self._mail_whitelist_files

        @property
        def announce_email(self) -> T.Optional[str]:
            """Mail address of a mailinglist where changes are announced."""
            return self._announce_email

    def __init__(self, fname=None):
        if not MailgunConfig.instance:
            MailgunConfig.instance = MailgunConfig.__MailgunConfig(fname)

    def __getattr__(self, name):
        return getattr(self.instance, name)
