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
from laniakea import LocalConfig

# Instance folder path
INSTANCE_FOLDER_PATH = '/var/lib/laniakea-webswview/'


class BaseConfig(object):

    PROJECT = 'Laniakea Software View'
    BUG_REPORT_URL = 'https://github.com/lkorigin/laniakea/issues'

    OS_NAME = LocalConfig().project_name

    LOG_STORAGE_URL = '/raw/logs'  # web URL where raw logs are stored by Rubicon
    APPSTREAM_MEDIA_URL = LocalConfig().archive_appstream_media_url

    # Get app root path, also can use flask.root_path.
    # ../../config.py
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    SECRET_KEY = os.urandom(16)

    DEBUG = False
    TESTING = False

    LOG_FOLDER = os.path.join(INSTANCE_FOLDER_PATH, 'logs')


class DefaultConfig(BaseConfig):

    DEBUG = True

    SENTRY_DSN = ""

    MAIL_HOST = ""
    FROM_ADDR = ""
    TO_ADDRS = [""]
    MAIL_USERNAME = ""
    MAIL_PASSWORD = ""
