# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os
import re
import email as pyemail
import tempfile
import subprocess

import jinja2 as jinja

from laniakea.logging import log
from laniakea.utils.deb822 import split_maintainer_field

from .config import MailgunConfig

re_re_mark = re.compile(r'^RE:')
re_whitespace_comment = re.compile(r"^\s*(#|$)")


class SendmailFailedError(Exception):
    """Failed to send mail via sendmail."""


class MailTemplateLoader:
    """Load & render E-Mail templates"""

    def __init__(self):
        thisfile = __file__
        if not os.path.isabs(thisfile):
            thisfile = os.path.normpath(os.path.join(os.getcwd(), thisfile))
        template_dir = os.path.join(os.path.dirname(thisfile), 'templates')
        self._env = jinja.Environment(loader=jinja.FileSystemLoader(template_dir), autoescape=jinja.select_autoescape())

    def render(self, template_id, **kwargs) -> str:
        template = self._env.get_template(template_id + '.tmpl')
        return template.render(**kwargs)


class MailSender:
    """E-Mail sender that uses sendmail"""

    def __init__(self):
        self._conf = MailgunConfig()
        self._whitelist = self._conf.mail_whitelist
        if self._conf.mail_whitelist_files:
            for path in self._conf.mail_whitelist_files:
                with open(path, 'r') as whitelist_in:
                    for line in whitelist_in:
                        if not re_whitespace_comment.match(line):
                            if re_re_mark.match(line):
                                self._whitelist.append(re.compile(re_re_mark.sub('', line.strip(), 1)))
                            else:
                                self._whitelist.append(re.compile(re.escape(line.strip())))

    def send(self, message: str):
        """Send an E-Mail via the system's sendmail command

        :param message: The email message
        """

        fd, filename = tempfile.mkstemp()
        with os.fdopen(fd, 'wt') as f:
            f.write(message)

        with open(filename) as message_in:
            message_raw = pyemail.message_from_file(message_in)

        if self._whitelist:
            # Fields to check.
            fields = ['To', 'Bcc', 'Cc']
            for field in fields:
                # Check each field
                value = message_raw.get(field, None)
                if value is not None:
                    match = []
                    for item in value.split(","):
                        rfc822_maint, name, email = split_maintainer_field(item.strip())
                        mail_whitelisted = 0
                        for wr in self._whitelist:
                            if wr.match(email):
                                mail_whitelisted = 1
                                break
                        if not mail_whitelisted:
                            log.info('Skipping %s since it is not whitelisted', item)
                            continue
                        match.append(item)

                    # Doesn't have any mail in whitelist so remove the header
                    if len(match) == 0:
                        del message_raw[field]
                    else:
                        message_raw.replace_header(field, ', '.join(match))

            # Change message fields in order if we don't have a To header
            if 'To' not in message_raw:
                fields.reverse()
                for field in fields:
                    if field in message_raw:
                        message_raw[fields[-1]] = message_raw[field]
                        del message_raw[field]
                        break
                else:
                    # Clean up any temporary files
                    # and return, as we removed all recipients.
                    os.unlink(filename)
                    return

            fd = os.open(filename, os.O_RDWR | os.O_EXCL, 0o700)
            with os.fdopen(fd, 'wt') as f:
                f.write(message_raw.as_string(True))

        # Invoke sendmail
        try:
            with open(filename, 'r') as fh:
                subprocess.check_output(self._conf.sendmail_cmd, stdin=fh, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise SendmailFailedError(e.output.rstrip())

        # Clean up any temporary files
        if message:
            os.unlink(filename)
