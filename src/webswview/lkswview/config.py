# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os

from laniakea import LocalConfig
from laniakea.db import config_get_project_name

# Instance folder path
INSTANCE_FOLDER_PATH = '/var/lib/laniakea/webswview/'


class BaseConfig:

    PROJECT = 'Laniakea SWV'
    BUG_REPORT_URL = 'https://github.com/lkhq/laniakea/issues'

    OS_NAME = config_get_project_name()

    LOG_STORAGE_URL = '/raw/logs'  # web URL where raw logs are stored by Rubicon
    APPSTREAM_MEDIA_URL = LocalConfig().archive_appstream_media_url
    ARCHIVE_URL = LocalConfig().archive_url

    #
    # Caching behavior
    #
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300

    # Get app root path, also can use flask.root_path.
    # ../../config.py
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    SECRET_KEY = os.urandom(16)

    DEBUG = False
    TESTING = False

    LOG_FOLDER = os.path.join(INSTANCE_FOLDER_PATH, 'logs')

    THEME = 'default'


class DefaultConfig(BaseConfig):

    DEBUG = False
    TESTING = False
    CACHE_TYPE = 'simple'


class DebugConfig(BaseConfig):

    DEBUG = True
    TESTING = True
    CACHE_TYPE = 'null'
