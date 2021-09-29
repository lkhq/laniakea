# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2021 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+

import os

# Instance folder path
INSTANCE_FOLDER_PATH = '/var/lib/laniakea-web/'


class BaseConfig:

    PROJECT = 'Laniakea Web'
    BUG_REPORT_URL = 'https://github.com/lkorigin/laniakea/issues'

    LOG_STORAGE_URL = '/raw/logs'  # web URL where raw logs are stored by Rubicon

    #
    # Caching behavior
    #
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300

    # Get app root path, also can use flask.root_path.
    # ../../config.py
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    DEBUG = False
    TESTING = False

    # http://flask.pocoo.org/docs/quickstart/#sessions
    SECRET_KEY = 'secret key'

    LOG_FOLDER = os.path.join(INSTANCE_FOLDER_PATH, 'logs')

    THEME = 'default'


class DefaultConfig(BaseConfig):

    DEBUG = False
    CACHE_TYPE = 'simple'


class DebugConfig(BaseConfig):

    DEBUG = True
    CACHE_TYPE = 'null'
